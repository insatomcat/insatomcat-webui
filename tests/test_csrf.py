# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Cross site request forgery protection.

The rule: an unsafe request that carries a session cookie must also carry the
matching token in a header. A foreign origin can make the browser send the
cookie, but it cannot read it to produce the header.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_an_unsafe_request_without_the_token_is_refused(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"})

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    # The session survives a refused forgery, otherwise the attack would still
    # log the operator out.
    assert client.get("/api/v1/auth/me").status_code == 200


def test_a_wrong_token_is_refused(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "secret"})

    response = client.post(
        "/api/v1/auth/logout", headers={"X-CSRF-Token": "not-the-token"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_the_matching_token_is_accepted(signed_in: TestClient) -> None:
    assert signed_in.post("/api/v1/auth/logout").status_code == 204


def test_login_itself_needs_no_token(client: TestClient) -> None:
    # There is no session yet, so there is no ambient authority to abuse.
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "secret"}
    )

    assert response.status_code == 200


def test_a_safe_request_needs_no_token(signed_in: TestClient) -> None:
    del signed_in.headers["X-CSRF-Token"]

    assert signed_in.get("/api/v1/node").status_code == 200
