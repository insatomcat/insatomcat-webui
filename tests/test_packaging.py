# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The quadlet and the image, checked for what a first deployment got wrong.

Nothing here can be caught by running the service: it is about what the
container is handed before Python starts. Each test corresponds to something
that had to be done by hand, or did not work, on a real machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
# Unfolded, because systemd continues a line with a trailing backslash and the
# directories are created by one command spread over three lines.
_QUADLET = (_ROOT / "seapath-webui.container").read_text().replace("\\\n", " ")
_DOCKERFILE = (_ROOT / "Dockerfile").read_text()

_VOLUMES = [
    line.split("=", 1)[1]
    for line in _QUADLET.splitlines()
    if line.startswith("Volume=")
]
_SOURCES = {volume.split(":", 1)[0] for volume in _VOLUMES}
_PRE_START = " ".join(
    line for line in _QUADLET.splitlines() if line.startswith("ExecStartPre=")
)


@pytest.mark.parametrize(
    "directory",
    [
        # The service's own state, needed by hand on the first real deployment.
        "/etc/seapath/webui",
        "/etc/seapath/inventory",
        "/var/lib/seapath-webui",
        # Absent from a machine that has never converged, and a missing bind
        # mount source is a container that does not start.
        "/etc/corosync",
        "/var/lib/pacemaker",
        "/etc/ceph",
        "/etc/tuned",
        "/run/tuned",
    ],
)
def test_a_mount_source_that_may_be_absent_is_created_by_the_unit(
    directory: str,
) -> None:
    # Dropping the quadlet on a machine and starting the unit has to be enough.
    assert directory in _PRE_START
    assert directory in _SOURCES


def test_the_journal_is_mounted_by_its_parent_and_never_created() -> None:
    # Creating /var/log/journal is what switches journald to a persistent
    # journal, so this service must neither create it nor require it. The
    # parents always exist.
    assert "/var/log/journal" not in _SOURCES
    assert "/var/log/journal" not in _PRE_START
    assert "/var/log" in _SOURCES
    assert "/run/log" in _SOURCES


def test_unit_states_are_asked_over_the_bus_and_not_the_private_socket() -> None:
    # systemctl running as root tries /run/systemd/private before the bus. It
    # connects, then checks the peer credentials, and a container with its own
    # PID namespace cannot be told the host's PID 1: the kernel reports pid 0
    # and systemd gives up with ENODATA. Mounting /run/systemd/system, which is
    # all `sd_booted()` looks at, rather than the whole of /run/systemd, is what
    # sends systemctl to the bus instead.
    assert "/run/systemd" not in _SOURCES
    assert "/run/systemd/system" in _SOURCES
    assert "/run/dbus" in _SOURCES


def test_the_host_accounts_are_read_through_a_directory_not_three_files() -> None:
    # `usermod` and `passwd` rename a new file over the old one, so a bind
    # mount of the file pins the inode the container started with: an operator
    # added to seapath-admin stayed locked out until the service was restarted.
    for pinned in ("/etc/passwd", "/etc/group", "/etc/shadow"):
        assert pinned not in _SOURCES
        assert f"ln -sf /run/host/etc/{Path(pinned).name} {pinned}" in _DOCKERFILE
    assert "/etc:/run/host/etc:ro" in _VOLUMES


def test_the_ansible_account_home_is_never_created_by_the_unit() -> None:
    # The service does not create the account, and inventing a home directory
    # for a user nobody created is a second problem, not a recovery. A machine
    # missing it was not installed from the SEAPATH ISO.
    assert "/home/ansible/.ssh" in _SOURCES
    assert "/home/ansible" not in _PRE_START
