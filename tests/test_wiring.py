# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""What the application factory wires by default.

The development switch replaces both the host adapter and the authentication,
which is convenient and dangerous in equal measure. These tests pin which one
a service gets, because the answer must never depend on a stray environment
variable that happens to be set on a machine.
"""

from __future__ import annotations

from app.core.auth import (
    DevAuthenticator,
    DevRoleDirectory,
    PamAuthenticator,
    UnixGroupDirectory,
)
from app.core.settings import Settings
from app.hosts.fake import FakeHostReader
from app.hosts.local import LocalHostReader
from app.main import create_app


def test_a_default_service_reads_the_real_machine_and_uses_pam(
    settings: Settings,
) -> None:
    application = create_app(settings=settings, session_secret=b"test-secret")

    assert isinstance(application.state.reader, LocalHostReader)
    assert isinstance(application.state.authenticator, PamAuthenticator)
    assert isinstance(application.state.role_directory, UnixGroupDirectory)


def test_the_development_switch_replaces_both_adapters_and_the_password_check(
    settings: Settings,
) -> None:
    settings = settings.model_copy(update={"use_fakes": True})

    application = create_app(settings=settings, session_secret=b"test-secret")

    assert isinstance(application.state.reader, FakeHostReader)
    assert isinstance(application.state.authenticator, DevAuthenticator)
    assert isinstance(application.state.role_directory, DevRoleDirectory)
