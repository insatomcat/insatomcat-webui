# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Authentication against the local Unix accounts, and role resolution.

There is no user database here, deliberately. Accounts are the host's accounts,
authenticated through PAM, and the role comes from Unix group membership. A
site that already manages its operators with SSSD or LDAP therefore manages the
UI's operators too, without this service growing an identity store it would
have to secure, replicate and audit.
"""

from __future__ import annotations

import grp
import pwd
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.core.settings import Settings


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        return _RANKS[self]

    def can(self, required: Role) -> bool:
        return self.rank >= required.rank


_RANKS = {Role.VIEWER: 0, Role.OPERATOR: 1, Role.ADMIN: 2}


@dataclass(frozen=True)
class User:
    username: str
    role: Role


class Authenticator(Protocol):
    """Verifies a password. Nothing more: the role is a separate question."""

    def authenticate(self, username: str, password: str) -> bool: ...


class RoleDirectory(Protocol):
    """Maps an account to a role, or to nothing at all."""

    def role_for(self, username: str) -> Role | None: ...


class PamAuthenticator:
    """PAM against the service file shipped in the image.

    The image carries its own `/etc/pam.d/seapath-webui` so the stack does not
    depend on what the host happens to have installed, and `/etc/shadow`,
    `/etc/passwd` and `/etc/group` are symlinks into the host's `/etc`, which
    the quadlet mounts read only, so `pam_unix` can do its job against the
    machine's real accounts as they are now rather than as they were when this
    container started.
    """

    def __init__(self, service: str) -> None:
        self._service = service
        # Resolved once, at startup, so a build that cannot import PAM crashes
        # with the reason in the journal. Deferring it would produce a service
        # that starts, answers, and refuses every password, which looks exactly
        # like a machine whose operators have all forgotten theirs.
        import pam as pam_module

        # python-pam renamed the class in 2.0 and kept the old name as an
        # alias. Accept either so the pin can move without a code change.
        self._factory = getattr(pam_module, "pam", None) or pam_module.PamAuthenticator

    def authenticate(self, username: str, password: str) -> bool:
        if not username or not password:
            return False
        return bool(
            self._factory().authenticate(username, password, service=self._service)
        )


class UnixGroupDirectory:
    """Role from Unix group membership, most privileged group winning."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def role_for(self, username: str) -> Role | None:
        settings = self._settings
        # D6: the ISO must produce a machine usable from a browser before any
        # Ansible run has created the SEAPATH groups, so root is an
        # administrator. This is PAM against the local account, not SSH, so the
        # hardening role's `PermitRootLogin no` does not contradict it.
        if settings.allow_root_login and username == "root":
            return Role.ADMIN
        for group, role in (
            (settings.admin_group, Role.ADMIN),
            (settings.operator_group, Role.OPERATOR),
            (settings.viewer_group, Role.VIEWER),
        ):
            if _is_member(username, group):
                return role
        return None


def _is_member(username: str, group: str) -> bool:
    try:
        entry = grp.getgrnam(group)
    except KeyError:
        # The groups are created by the Ansible role. A machine that has never
        # converged simply has no members, which is not an error.
        return False
    if username in entry.gr_mem:
        return True
    try:
        return pwd.getpwnam(username).pw_gid == entry.gr_gid
    except KeyError:
        return False


class DevAuthenticator:
    """Accepts any account with any password.

    Reachable only behind the `use_fakes` switch, which also replaces the host
    adapter with invented readings, so a service configured this way tells an
    operator nothing true about a machine and is useless on one. It exists
    because PAM cannot authenticate a SEAPATH account on a developer's laptop,
    and a UI nobody can open is a UI nobody reviews.
    """

    def authenticate(self, username: str, password: str) -> bool:
        return bool(username and password)


class DevRoleDirectory:
    """Grants administrator to anyone who authenticates. Same switch, same risk."""

    def role_for(self, username: str) -> Role | None:
        return Role.ADMIN
