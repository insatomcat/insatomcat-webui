# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The node view, composed from the read only adapter.

The service layer decides what is worth showing and what a reading means for
an operator. The adapter only decides how to read it.

Unit states, the journal and the clock offset used to be here. They are live
state, every node runs prometheus-node-exporter, and duplicating it cost this
container a route to the host's systemd. See docs/deployment.md.
"""

from __future__ import annotations

from datetime import datetime

from app import __version__
from app.hosts.models import (
    CpuReading,
    DisksReading,
    NetworkReading,
    NodeMode,
    Reading,
)
from app.hosts.reader import HostReader


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


class NodeService:
    def __init__(self, reader: HostReader, collection_version: str) -> None:
        self._reader = reader
        self._collection_version = collection_version

    def summary(self) -> NodeSummary:
        identity = self._reader.node_identity()
        return NodeSummary(
            hostname=identity.hostname,
            mode=identity.mode,
            kernel_release=identity.kernel_release,
            distribution=identity.distribution,
            uptime_seconds=identity.uptime_seconds,
            boot_time=identity.boot_time,
            collection_version=self._collection_version,
            warnings=identity.warnings,
        )

    def cpu(self) -> CpuReading:
        return self._reader.cpu()

    def network(self) -> NetworkReading:
        return self._reader.network()

    def disks(self) -> DisksReading:
        return self._reader.disks()
