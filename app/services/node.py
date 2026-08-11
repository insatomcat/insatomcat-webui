# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The node view, composed from the read only adapter.

The service layer decides what is worth showing and what a reading means for
an operator. The adapter only decides how to read it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app import __version__
from app.core.errors import ApiError
from app.hosts.models import (
    CpuReading,
    DisksReading,
    LogReading,
    NetworkReading,
    NodeMode,
    Reading,
    ServicesReading,
    ServiceUnit,
    TimeReading,
)
from app.hosts.reader import HostReader

# The units an operator looks at on a SEAPATH machine, in the order they are
# worth reading. The list is an allowlist for the journal endpoint too: an
# arbitrary unit name from a browser would be a way to read anything the
# journal holds, which is more than the viewer role should see.
UNITS_OF_INTEREST = (
    "seapath-webui.service",
    "libvirtd.service",
    "openvswitch-switch.service",
    "timemaster.service",
    "corosync.service",
    "pacemaker.service",
    "ceph.target",
    "ssh.service",
    "snmpd.service",
    "prometheus-node-exporter.service",
    "cockpit.socket",
    "tuned.service",
)

_MAX_LOG_LINES = 1000


class NodeSummary(Reading):
    """What `GET /api/v1/node` answers."""

    hostname: str
    mode: NodeMode
    kernel_release: str | None = None
    distribution: str | None = None
    uptime_seconds: float | None = None
    boot_time: datetime | None = None

    # The version of the SEAPATH image is recorded in the installation media
    # metadata and is not written anywhere on the installed system, so the node
    # cannot report it. What identifies what this service will actually run is
    # the collection shipped in its image, which is reported instead.
    seapath_version: str | None = None
    collection_version: str
    webui_version: str = __version__

    # Filled from M1 on, when the inventory repository exists. Reported as
    # unknown rather than omitted so the field is stable in the schema.
    inventory_commit: str | None = None
    role: str | None = None

    units: list[ServiceUnit] = Field(default_factory=list)


class NodeService:
    def __init__(self, reader: HostReader, collection_version: str) -> None:
        self._reader = reader
        self._collection_version = collection_version

    def summary(self) -> NodeSummary:
        identity = self._reader.node_identity()
        services = self._reader.services(list(UNITS_OF_INTEREST))
        return NodeSummary(
            hostname=identity.hostname,
            mode=identity.mode,
            kernel_release=identity.kernel_release,
            distribution=identity.distribution,
            uptime_seconds=identity.uptime_seconds,
            boot_time=identity.boot_time,
            collection_version=self._collection_version,
            units=services.units,
            warnings=[*identity.warnings, *services.warnings],
        )

    def cpu(self) -> CpuReading:
        return self._reader.cpu()

    def network(self) -> NetworkReading:
        return self._reader.network()

    def time_sync(self) -> TimeReading:
        return self._reader.time_sync()

    def services(self) -> ServicesReading:
        return self._reader.services(list(UNITS_OF_INTEREST))

    def disks(self) -> DisksReading:
        return self._reader.disks()

    def logs(self, unit: str, lines: int) -> LogReading:
        if unit not in UNITS_OF_INTEREST:
            raise ApiError(
                "unit_not_allowed",
                f"{unit} is not one of the units this view exposes.",
                404,
                {"allowed": list(UNITS_OF_INTEREST)},
            )
        return self._reader.logs(unit, max(1, min(lines, _MAX_LOG_LINES)))
