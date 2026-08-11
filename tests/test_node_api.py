# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The read only node API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.node import UNITS_OF_INTEREST

_ENDPOINTS = [
    "/api/v1/node",
    "/api/v1/node/cpu",
    "/api/v1/node/network",
    "/api/v1/node/time",
    "/api/v1/node/services",
    "/api/v1/node/disks",
]


@pytest.mark.parametrize("path", _ENDPOINTS)
def test_every_reading_needs_a_session(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401


def test_the_summary_reports_the_machine_and_the_collection(
    signed_in: TestClient,
) -> None:
    body = signed_in.get("/api/v1/node").json()

    assert body["hostname"] == "seapath-machine"
    assert body["mode"] == "standalone"
    assert body["kernel_release"] == "6.1.0-18-rt-amd64"
    assert body["collection_version"] == "test"
    # No inventory before M1, and the field says so rather than disappearing.
    assert body["inventory_commit"] is None
    assert [unit["unit"] for unit in body["units"]] == list(UNITS_OF_INTEREST)


def test_the_cpu_view_separates_isolated_from_housekeeping(
    signed_in: TestClient,
) -> None:
    body = signed_in.get("/api/v1/node/cpu").json()

    assert body["isolated"] == [4, 5, 6, 7]
    assert body["housekeeping"] == [0, 1, 2, 3]
    assert len(body["topology"]) == 8
    assert all(entry["isolated"] for entry in body["topology"][4:])


def test_the_disk_view_carries_the_stable_path_ceph_needs(
    signed_in: TestClient,
) -> None:
    body = signed_in.get("/api/v1/node/disks").json()
    free = [device for device in body["devices"] if not device["claimed"]]

    assert len(free) == 1
    assert free[0]["by_path"].startswith("/dev/disk/by-path/")


def test_the_journal_is_limited_to_the_units_the_view_exposes(
    signed_in: TestClient,
) -> None:
    allowed = signed_in.get("/api/v1/node/logs?unit=libvirtd.service")
    refused = signed_in.get("/api/v1/node/logs?unit=sshd@1234.service")

    assert allowed.status_code == 200
    assert refused.status_code == 404
    assert refused.json()["error"]["code"] == "unit_not_allowed"


def test_an_unavailable_journal_is_reported_rather_than_faked(
    client: TestClient, reader
) -> None:
    reader.journal_available = False
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"})

    body = client.get("/api/v1/node/logs?unit=libvirtd.service").json()

    assert body["lines"] == []
    assert body["warnings"]


def test_the_openapi_schema_is_where_the_api_document_says(
    client: TestClient,
) -> None:
    schema = client.get("/api/v1/openapi.json")

    assert schema.status_code == 200
    assert "/api/v1/node" in schema.json()["paths"]
