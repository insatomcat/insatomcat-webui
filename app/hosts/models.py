# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""What the read only adapter returns.

Every reading carries `warnings`. A field that could not be read is `None` next
to a sentence saying why, because on a substation hypervisor "unknown" and
"zero" must never look alike.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Reading(BaseModel):
    warnings: list[str] = Field(default_factory=list)


class NodeMode(str, Enum):
    STANDALONE = "standalone"
    CLUSTER = "cluster"
    UNKNOWN = "unknown"


class NodeIdentity(Reading):
    hostname: str
    kernel_release: str | None = None
    distribution: str | None = None
    distribution_id: str | None = None
    distribution_version: str | None = None
    uptime_seconds: float | None = None
    boot_time: datetime | None = None
    mode: NodeMode = NodeMode.UNKNOWN


class CpuTopologyEntry(BaseModel):
    cpu: int
    socket: int | None = None
    core: int | None = None
    online: bool = True
    isolated: bool = False
    busy_percent: float | None = None


class CpuReading(Reading):
    model: str | None = None
    present: int | None = None
    online: int | None = None
    isolated: list[int] = Field(default_factory=list)
    isolated_source: str | None = None
    nohz_full: list[int] = Field(default_factory=list)
    housekeeping: list[int] = Field(default_factory=list)
    tuned_profile: str | None = None
    load_average: list[float] | None = None
    topology: list[CpuTopologyEntry] = Field(default_factory=list)
    kernel_cmdline: str | None = None


class InterfaceAddress(BaseModel):
    address: str
    prefix_length: int | None = None
    family: str


class NetworkInterface(BaseModel):
    name: str
    kind: str | None = None
    mac: str | None = None
    operstate: str | None = None
    carrier: bool | None = None
    mtu: int | None = None
    speed_mbps: int | None = None
    driver: str | None = None
    master: str | None = None
    addresses: list[InterfaceAddress] = Field(default_factory=list)


class NetworkReading(Reading):
    interfaces: list[NetworkInterface] = Field(default_factory=list)
    default_route_interface: str | None = None
    default_gateway: str | None = None


class PtpClock(BaseModel):
    device: str
    clock_name: str | None = None


class TimeReading(Reading):
    synchronised: bool | None = None
    source: str | None = None
    reference: str | None = None
    stratum: int | None = None
    offset_seconds: float | None = None
    ptp_clocks: list[PtpClock] = Field(default_factory=list)
    system_time: datetime | None = None


class ServiceUnit(BaseModel):
    unit: str
    load_state: str | None = None
    active_state: str | None = None
    sub_state: str | None = None
    description: str | None = None


class ServicesReading(Reading):
    units: list[ServiceUnit] = Field(default_factory=list)


class BlockDevice(BaseModel):
    name: str
    path: str
    by_path: str | None = None
    size_bytes: int | None = None
    model: str | None = None
    serial: str | None = None
    rotational: bool | None = None
    removable: bool | None = None
    read_only: bool | None = None
    partitions: list[str] = Field(default_factory=list)
    holders: list[str] = Field(default_factory=list)
    claimed: bool | None = None
    claim_reason: str | None = None


class DisksReading(Reading):
    devices: list[BlockDevice] = Field(default_factory=list)


class LogLine(BaseModel):
    timestamp: datetime | None = None
    unit: str | None = None
    priority: int | None = None
    message: str


class LogReading(Reading):
    unit: str
    lines: list[LogLine] = Field(default_factory=list)
