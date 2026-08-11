# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures.

Nothing here touches a SEAPATH machine, a cluster, libvirt or a container. The
application is built with the fakes in place of the two host adapters, which is
the whole reason those adapters exist.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.auth import Role
from app.core.settings import Settings
from app.hosts.fake import FakeHostReader
from app.main import create_app
from tests.fakes import FakeAuthenticator, FakeRoleDirectory

# The service is HTTPS only and sets its cookies `Secure`, so a test client on
# http:// would silently drop every session cookie.
BASE_URL = "https://testserver"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        state_dir=tmp_path / "state",
        host_root=tmp_path / "host",
        collection_version="test",
    )


@pytest.fixture
def reader() -> FakeHostReader:
    return FakeHostReader()


@pytest.fixture
def authenticator() -> FakeAuthenticator:
    return FakeAuthenticator(
        {"admin": "secret", "viewer": "secret", "nobody": "secret"}
    )


@pytest.fixture
def directory() -> FakeRoleDirectory:
    return FakeRoleDirectory({"admin": Role.ADMIN, "viewer": Role.VIEWER})


@pytest.fixture
def client(
    settings: Settings,
    reader: FakeHostReader,
    authenticator: FakeAuthenticator,
    directory: FakeRoleDirectory,
) -> Iterator[TestClient]:
    application = create_app(
        settings=settings,
        reader=reader,
        authenticator=authenticator,
        role_directory=directory,
        session_secret=b"test-secret",
    )
    with TestClient(application, base_url=BASE_URL) as test_client:
        yield test_client


@pytest.fixture
def signed_in(client: TestClient) -> TestClient:
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "secret"}
    )
    assert response.status_code == 200
    # The front end reads the token from the cookie; the test client does the
    # same rather than trusting the login response body.
    client.headers["X-CSRF-Token"] = client.cookies["seapath_csrf"]
    return client
