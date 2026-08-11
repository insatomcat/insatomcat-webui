# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The browser facing pages.

The pages are thin. Everything they display comes from `/api/v1`, which is the
same surface an automation client uses, so a screen can never show something
the API cannot answer.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.core.security import current_session

_UI_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_UI_DIR / "templates"))


def install(app: FastAPI) -> None:
    app.mount(
        "/static",
        StaticFiles(directory=str(_UI_DIR / "static")),
        name="static",
    )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request):
        if current_session(request) is None:
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(
            request, "node.html", {"version": __version__}
        )

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login(request: Request):
        if current_session(request) is not None:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse(
            request, "login.html", {"version": __version__}
        )
