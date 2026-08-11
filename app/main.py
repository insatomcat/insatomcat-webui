# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Application factory.

Everything the request handlers need is built here and hung on `app.state`,
which keeps the wiring visible in one place and makes the test suite a matter
of building an application with the fakes instead of the real adapters.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import v1
from app.core.auth import (
    Authenticator,
    DevAuthenticator,
    DevRoleDirectory,
    PamAuthenticator,
    RoleDirectory,
    UnixGroupDirectory,
)
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.security import CsrfMiddleware
from app.core.sessions import SessionStore
from app.core.settings import Settings, get_settings
from app.core.tls import ensure_session_secret
from app.hosts.fake import FakeHostReader
from app.hosts.local import LocalHostReader
from app.hosts.reader import HostReader
from app.services.node import NodeService
from app.ui import routes as ui_routes

logger = logging.getLogger(__name__)

_DESCRIPTION = """
Node local management API for a SEAPATH machine.

This service does not configure machines. It edits the inventory and runs the
upstream SEAPATH playbooks. Anything that changes a host is an Ansible run.
"""


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "seapath-webui %s starting, collection %s",
        __version__,
        settings.collection_version,
    )
    yield
    logger.info("seapath-webui stopping")


def create_app(
    settings: Settings | None = None,
    reader: HostReader | None = None,
    authenticator: Authenticator | None = None,
    role_directory: RoleDirectory | None = None,
    session_secret: bytes | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    if settings.use_fakes:
        logger.warning(
            "SEAPATH_WEBUI_USE_FAKES is set: this service is serving invented "
            "readings and accepting any password. It must not be used on a "
            "real machine."
        )

    if reader is None:
        reader = (
            FakeHostReader()
            if settings.use_fakes
            else LocalHostReader(root=settings.host_root)
        )
    if authenticator is None:
        authenticator = (
            DevAuthenticator()
            if settings.use_fakes
            else PamAuthenticator(settings.pam_service)
        )
    if role_directory is None:
        role_directory = (
            DevRoleDirectory() if settings.use_fakes else UnixGroupDirectory(settings)
        )

    app = FastAPI(
        title="seapath-webui",
        version=__version__,
        description=_DESCRIPTION,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    app.state.settings = settings
    app.state.reader = reader
    app.state.authenticator = authenticator
    app.state.role_directory = role_directory
    app.state.sessions = SessionStore(
        secret=session_secret or ensure_session_secret(settings),
        ttl_seconds=settings.session_ttl_seconds,
    )
    app.state.node_service = NodeService(reader, settings.collection_version)

    install_error_handlers(app)
    app.add_middleware(CsrfMiddleware)
    app.include_router(v1.router)
    ui_routes.install(app)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        # Unauthenticated on purpose: it says the process answers, and nothing
        # about the machine.
        return {"status": "ok", "version": __version__}

    return app
