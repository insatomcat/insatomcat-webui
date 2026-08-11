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

    def _page(request: Request, template: str, page: str):
        if current_session(request) is None:
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(
            request,
            template,
            {"version": __version__, "page": page, "nav": True},
        )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request):
        return _page(request, "node.html", "node")

    @app.get("/setup", response_class=HTMLResponse, include_in_schema=False)
    def setup(request: Request):
        return _page(request, "setup.html", "setup")

    @app.get("/runs", response_class=HTMLResponse, include_in_schema=False)
    def runs(request: Request):
        return _page(request, "runs.html", "runs")

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login(request: Request):
        if current_session(request) is not None:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse(
            request, "login.html", {"version": __version__, "nav": False}
        )
