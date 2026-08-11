# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Fakes for what the tests must not depend on: PAM and the host."""

from __future__ import annotations

from app.core.auth import Role
from app.hosts.reader import CommandResult


class FakeAuthenticator:
    def __init__(self, accounts: dict[str, str] | None = None) -> None:
        self.accounts = accounts or {"admin": "secret"}

    def authenticate(self, username: str, password: str) -> bool:
        return self.accounts.get(username) == password


class FakeRoleDirectory:
    def __init__(self, roles: dict[str, Role] | None = None) -> None:
        self.roles = roles or {"admin": Role.ADMIN}

    def role_for(self, username: str) -> Role | None:
        return self.roles.get(username)


class FakeCommandRunner:
    """Replays recorded output, keyed by the first two words of the command.

    An unregistered command fails the way a missing binary does, so a test that
    forgets to record one exercises the degraded path rather than crashing.
    """

    def __init__(self, responses: dict[str, CommandResult] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[list[str]] = []

    def run(self, argv: list[str], timeout: float = 5.0) -> CommandResult:
        del timeout
        self.calls.append(list(argv))
        for key, result in self.responses.items():
            if " ".join(argv).startswith(key):
                return result
        return CommandResult(127, "", f"{argv[0]}: not found in this image")
