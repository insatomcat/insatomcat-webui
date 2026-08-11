# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The node view. Read only, in the strong sense: nothing here changes a host.

Every endpoint is open to the viewer role, which is the whole point of having
one. Configuration lives elsewhere, and from M1 it is reached by editing the
inventory and running a playbook.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import Role
from app.core.security import require_role
from app.hosts.models import (
    CpuReading,
    DisksReading,
    LogReading,
    NetworkReading,
    ServicesReading,
    TimeReading,
)
from app.services.node import NodeService, NodeSummary

router = APIRouter(
    prefix="/node",
    tags=["node"],
    dependencies=[Depends(require_role(Role.VIEWER))],
)


def _service(request: Request) -> NodeService:
    return request.app.state.node_service


@router.get("", response_model=NodeSummary)
def node(request: Request) -> NodeSummary:
    return _service(request).summary()


@router.get("/cpu", response_model=CpuReading)
def cpu(request: Request) -> CpuReading:
    return _service(request).cpu()


@router.get("/network", response_model=NetworkReading)
def network(request: Request) -> NetworkReading:
    return _service(request).network()


@router.get("/time", response_model=TimeReading)
def time(request: Request) -> TimeReading:
    return _service(request).time_sync()


@router.get("/services", response_model=ServicesReading)
def services(request: Request) -> ServicesReading:
    return _service(request).services()


@router.get("/disks", response_model=DisksReading)
def disks(request: Request) -> DisksReading:
    return _service(request).disks()


@router.get("/logs", response_model=LogReading)
def logs(
    request: Request,
    unit: str = Query(description="One of the units listed by GET /node/services"),
    lines: int = Query(default=100, ge=1, le=1000),
) -> LogReading:
    return _service(request).logs(unit, lines)
