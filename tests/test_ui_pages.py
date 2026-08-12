# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The pages, checked for the things a screenshot would not catch."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("path", ["/", "/setup", "/runs"])
def test_every_page_needs_a_session(client: TestClient, path: str) -> None:
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.parametrize(
    ("path", "script"),
    [("/", "node.js"), ("/setup", "setup.js"), ("/runs", "runs.js")],
)
def test_each_page_loads_its_own_script_and_the_shared_chrome(
    signed_in: TestClient, path: str, script: str
) -> None:
    body = signed_in.get(path).text

    assert script in body
    assert "chrome.js" in body
    assert "api.js" in body


def test_the_configuration_page_says_what_saving_does_and_does_not_do(
    signed_in: TestClient,
) -> None:
    body = signed_in.get("/setup").text

    # The two acts are separate, and the page has to say so: deciding what a
    # machine should be is not the same as making it so.
    assert "saving" in body and "commit" in body
    assert "applying runs the SEAPATH playbooks" in body


def test_the_real_time_fields_are_behind_a_collapsed_expert_section(
    signed_in: TestClient,
) -> None:
    body = signed_in.get("/setup").text

    # The rule is that the UI never makes a real time relevant change look
    # routine.
    assert '<details class="expert">' in body
    assert "isolcpus" in body
    assert "Latency is the product" in body


def test_the_apply_confirmation_makes_the_machine_be_typed_out(
    signed_in: TestClient,
) -> None:
    body = signed_in.get("/setup").text

    # This is the single most dangerous button in the product, and it has to
    # look like it.
    assert "confirm-input" in body
    assert "to confirm" in body


def test_a_hidden_element_is_hidden_whatever_its_display_rule(
    signed_in: TestClient,
) -> None:
    body = signed_in.get("/setup").text
    css = signed_in.get("/static/style.css").text

    # Everything in this UI is shown and dismissed with the `hidden` attribute,
    # and a `display` rule in the stylesheet beats the attribute. The
    # confirmation modal is `display: grid`, so without this rule it is on
    # screen from the moment the page loads, over a page nobody asked to leave,
    # and Cancel does not dismiss it.
    assert '<div class="modal" id="confirm" hidden>' in body
    assert "[hidden]" in css
    assert "display: none !important" in css


def test_a_table_scrolls_inside_its_card_rather_than_over_the_next_one(
    signed_in: TestClient,
) -> None:
    body = signed_in.get("/").text
    css = signed_in.get("/static/style.css").text

    # A `by-path` name is longer than half a page, and the cards sit in
    # flexible grid tracks, so nothing widens a card to fit its content. The
    # tables of machine values take the whole width, and scroll inside their
    # card when even that is not enough.
    assert body.count('class="card wide"') == 2
    assert body.count('<div class="table-scroll">') == 2
    assert ".card.wide" in css
    assert "overflow-x: auto" in css


def test_the_login_page_carries_no_navigation(client: TestClient) -> None:
    body = client.get("/login").text

    assert "Sign out" not in body
    assert "chrome.js" not in body


def test_the_static_assets_are_served(signed_in: TestClient) -> None:
    for asset in ("api.js", "chrome.js", "node.js", "setup.js", "runs.js", "style.css"):
        assert signed_in.get(f"/static/{asset}").status_code == 200
