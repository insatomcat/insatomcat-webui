# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Authentication, roles and sessions."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.core.auth import Role, UnixGroupDirectory, User
from app.core.sessions import SessionStore
from app.core.settings import Settings


def test_login_sets_a_session_and_reports_the_identity(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "secret"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert body["node"] == "seapath-machine"
    assert body["mode"] == "standalone"
    assert client.cookies["seapath_session"]
    assert client.cookies["seapath_csrf"] == body["csrf_token"]


def test_a_wrong_password_does_not_say_whether_the_account_exists(
    client: TestClient,
) -> None:
    unknown = client.post(
        "/api/v1/auth/login", json={"username": "ghost", "password": "secret"}
    )
    wrong = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
    assert unknown.json()["error"]["code"] == "invalid_credentials"


def test_an_account_in_no_seapath_group_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "secret"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "no_role"
    assert "seapath-admin" in response.json()["error"]["message"]


def test_me_requires_a_session(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_logout_invalidates_the_session(signed_in: TestClient) -> None:
    assert signed_in.post("/api/v1/auth/logout").status_code == 204
    assert signed_in.get("/api/v1/auth/me").status_code == 401


def test_a_forged_cookie_is_rejected_before_the_store_is_consulted(
    client: TestClient,
) -> None:
    client.cookies.set("seapath_session", "forged.deadbeef", domain="testserver")

    assert client.get("/api/v1/auth/me").status_code == 401


def test_the_viewer_role_cannot_reach_an_operator_endpoint(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"username": "viewer", "password": "secret"})

    # The node view is open to viewers, which is what the role is for.
    assert client.get("/api/v1/node").status_code == 200
    assert Role.VIEWER.can(Role.VIEWER)
    assert not Role.VIEWER.can(Role.OPERATOR)
    assert Role.ADMIN.can(Role.OPERATOR)


def test_a_session_expires(settings: Settings) -> None:
    store = SessionStore(secret=b"test-secret", ttl_seconds=0)
    session = store.create(User("admin", Role.ADMIN))

    time.sleep(0.01)

    assert store.get(session.id) is None
    del settings


def test_root_is_an_administrator_so_the_iso_is_usable_before_ansible_runs(
    settings: Settings,
) -> None:
    # D6, applied: the machine must be reachable from a browser before any
    # playbook has created the SEAPATH groups.
    assert UnixGroupDirectory(settings).role_for("root") == Role.ADMIN


def test_root_can_be_refused_once_a_site_has_other_accounts(
    settings: Settings,
) -> None:
    settings = settings.model_copy(update={"allow_root_login": False})

    assert UnixGroupDirectory(settings).role_for("root") is None
