# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The real read only adapter, against a recorded machine.

These tests are the ones that would catch a parser breaking on a kernel that
formats something differently. They run on a laptop because the filesystem root
is a parameter and every command goes through the injected runner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.hosts.local import LocalHostReader, parse_cpu_list
from app.hosts.models import NodeMode
from app.hosts.reader import CommandResult
from tests.fakes import FakeCommandRunner
from tests.hostfixture import build_host_tree, write_proc_stat


@pytest.fixture
def host(tmp_path: Path) -> Path:
    return build_host_tree(tmp_path / "host")


@pytest.fixture
def runner() -> FakeCommandRunner:
    return FakeCommandRunner(
        {
            "ip -j addr show": CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "ifname": "eno1",
                            "addr_info": [
                                {
                                    "family": "inet",
                                    "local": "192.168.200.121",
                                    "prefixlen": 24,
                                }
                            ],
                        },
                        {"ifname": "lo", "addr_info": []},
                    ]
                ),
                "",
            ),
            "systemctl list-units": CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "unit": "libvirtd.service",
                            "load": "loaded",
                            "active": "active",
                            "sub": "running",
                            "description": "Virtualization daemon",
                        }
                    ]
                ),
                "",
            ),
            "chronyc -c tracking": CommandResult(
                0,
                "7F7F0101,PTP,1,1754899200.0,0.000000132,0.000000101,"
                "0.000000090,-0.001,0.000,0.010,0.000010,0.000030,4,Normal\n",
                "",
            ),
            "journalctl": CommandResult(
                0,
                "\n".join(
                    [
                        json.dumps(
                            {
                                "__REALTIME_TIMESTAMP": "1754899200000000",
                                "_SYSTEMD_UNIT": "libvirtd.service",
                                "PRIORITY": "6",
                                "MESSAGE": "libvirtd started",
                            }
                        ),
                        json.dumps(
                            {
                                "__REALTIME_TIMESTAMP": "1754899201000000",
                                "_SYSTEMD_UNIT": "libvirtd.service",
                                "PRIORITY": "6",
                                # journalctl renders a non UTF-8 message as
                                # a list of byte values.
                                "MESSAGE": [104, 105],
                            }
                        ),
                    ]
                ),
                "",
            ),
        }
    )


@pytest.fixture
def reader(host: Path, runner: FakeCommandRunner) -> LocalHostReader:
    return LocalHostReader(root=host, runner=runner)


def test_the_hostname_comes_from_the_host_not_the_container(
    reader: LocalHostReader,
) -> None:
    identity = reader.node_identity()

    assert identity.hostname == "node1"
    assert identity.warnings == []


def test_a_missing_hostname_mount_is_called_out(tmp_path: Path) -> None:
    identity = LocalHostReader(root=tmp_path / "empty").node_identity()

    assert any("etc/hostname" in warning for warning in identity.warnings)


def test_a_machine_without_corosync_conf_reads_as_standalone(
    reader: LocalHostReader,
) -> None:
    # The file only appears once cluster_setup_ha.yaml has run, so a standalone
    # node is the normal case, not a degraded reading.
    assert reader.node_identity().mode is NodeMode.STANDALONE


def test_corosync_conf_makes_it_a_cluster_member(
    reader: LocalHostReader, host: Path
) -> None:
    (host / "etc/corosync/corosync.conf").write_text("totem {}\n")

    assert reader.node_identity().mode is NodeMode.CLUSTER


def test_the_isolated_set_is_read_from_sysfs(reader: LocalHostReader) -> None:
    cpu = reader.cpu()

    assert cpu.isolated == [4, 5, 6, 7]
    assert cpu.isolated_source == "sysfs"
    assert cpu.housekeeping == [0, 1, 2, 3]
    assert cpu.tuned_profile == "realtime"
    assert cpu.model.startswith("Intel(R) Xeon(R)")


def test_the_isolated_set_falls_back_to_the_kernel_command_line(
    reader: LocalHostReader, host: Path
) -> None:
    # An older kernel does not export /sys/devices/system/cpu/isolated.
    (host / "sys/devices/system/cpu/isolated").write_text("\n")

    cpu = reader.cpu()

    assert cpu.isolated == [4, 5, 6, 7]
    assert cpu.isolated_source == "cmdline"


def test_a_machine_with_no_isolation_says_so(
    reader: LocalHostReader, host: Path
) -> None:
    (host / "sys/devices/system/cpu/isolated").write_text("\n")
    (host / "proc/cmdline").write_text("BOOT_IMAGE=/vmlinuz root=/dev/sda1 ro\n")

    cpu = reader.cpu()

    assert cpu.isolated == []
    assert any("seapath_setup_main" in warning for warning in cpu.warnings)


def test_cpu_busy_is_a_rate_between_two_polls_not_an_average_since_boot(
    reader: LocalHostReader, host: Path
) -> None:
    first = reader.cpu()
    assert all(entry.busy_percent is None for entry in first.topology)

    # Half of the elapsed jiffies were busy.
    write_proc_stat(host, busy=1500, idle=9500)
    second = reader.cpu()

    assert all(entry.busy_percent == 50.0 for entry in second.topology)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0-3", [0, 1, 2, 3]),
        ("0-3,8", [0, 1, 2, 3, 8]),
        ("4", [4]),
        ("", []),
        (None, []),
        # `isolcpus` accepts flags before the list.
        ("nohz,domain,4-7", [4, 5, 6, 7]),
    ],
)
def test_the_kernel_cpu_list_syntax(raw: str | None, expected: list[int]) -> None:
    assert parse_cpu_list(raw) == expected


def test_addresses_come_from_iproute_and_links_from_sysfs(
    reader: LocalHostReader,
) -> None:
    network = reader.network()
    interfaces = {item.name: item for item in network.interfaces}

    assert interfaces["eno1"].driver == "igb"
    assert interfaces["eno1"].speed_mbps == 1000
    assert interfaces["eno1"].addresses[0].address == "192.168.200.121"
    assert interfaces["eno1"].addresses[0].prefix_length == 24
    # A virtual device reports -1, which is not a speed.
    assert interfaces["ovsbr0"].speed_mbps is None
    assert network.default_route_interface == "eno1"
    assert network.default_gateway == "192.168.200.1"


def test_missing_iproute_degrades_with_the_reason(host: Path) -> None:
    network = LocalHostReader(root=host, runner=FakeCommandRunner()).network()

    assert network.interfaces
    assert all(item.addresses == [] for item in network.interfaces)
    assert any("addresses are unavailable" in w for w in network.warnings)


def test_the_time_offset_comes_from_chrony(reader: LocalHostReader) -> None:
    time_sync = reader.time_sync()

    assert time_sync.reference == "PTP"
    assert time_sync.stratum == 1
    assert time_sync.offset_seconds == pytest.approx(1.32e-07)
    assert time_sync.synchronised is True
    assert [clock.clock_name for clock in time_sync.ptp_clocks] == ["ice-ptp"]


def test_an_unreachable_chronyd_leaves_the_offset_unknown(host: Path) -> None:
    time_sync = LocalHostReader(root=host, runner=FakeCommandRunner()).time_sync()

    # Never a zero offset: an operator would read that as "in sync".
    assert time_sync.offset_seconds is None
    assert any("offset is unavailable" in w for w in time_sync.warnings)


def test_a_unit_systemd_does_not_know_is_reported_as_absent(
    reader: LocalHostReader,
) -> None:
    services = reader.services(["libvirtd.service", "corosync.service"])
    states = {unit.unit: unit for unit in services.units}

    assert states["libvirtd.service"].active_state == "active"
    # "corosync is not installed" is itself an answer worth showing.
    assert states["corosync.service"].load_state == "not-found"


def test_disks_carry_the_by_path_name_and_their_claim_state(
    reader: LocalHostReader,
) -> None:
    devices = {device.name: device for device in reader.disks().devices}

    assert set(devices) == {"sda", "sdb", "sdc"}
    assert devices["sda"].claimed is True
    assert devices["sda"].partitions == ["sda1", "sda2"]
    assert devices["sdb"].claimed is False
    assert devices["sdb"].by_path == ("/dev/disk/by-path/pci-0000:03:00.0-scsi-0:2:1:0")
    assert devices["sdb"].size_bytes == 3750748848 * 512
    assert devices["sdc"].claimed is True
    assert devices["sdc"].holders == ["dm-0"]


def test_the_by_path_name_of_a_disk_is_never_a_partition_link(
    reader: LocalHostReader,
) -> None:
    # Choosing sda1's link for sda would put a partition in ceph_osd_disks.
    devices = {device.name: device for device in reader.disks().devices}

    assert devices["sda"].by_path == ("/dev/disk/by-path/pci-0000:03:00.0-scsi-0:2:0:0")


def test_the_journal_is_parsed_including_a_non_utf8_message(
    reader: LocalHostReader,
) -> None:
    log = reader.logs("libvirtd.service", 100)

    assert [line.message for line in log.lines] == ["libvirtd started", "hi"]
    assert log.lines[0].priority == 6


def test_a_missing_journalctl_is_reported_rather_than_an_empty_log(
    host: Path,
) -> None:
    log = LocalHostReader(root=host, runner=FakeCommandRunner()).logs("ssh.service", 10)

    assert log.lines == []
    assert any("journal is unavailable" in w for w in log.warnings)
