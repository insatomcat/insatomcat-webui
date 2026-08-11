# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Sessions and CSRF tokens.

Sessions live in memory. They are not persisted and not shared between nodes,
on purpose: a session is a browser tab, not desired state, and AGENTS.md says
there is no database here. A restart logs everyone out, which on a service with
`Restart=always` is a visible event rather than a silent one.

The cookie carries the session identifier signed with the node's session
secret, so a forged cookie is rejected before it reaches the store.
"""

from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256

from app.core.auth import Role, User

_ID_BYTES = 32


@dataclass
class Session:
    id: str
    username: str
    role: Role
    csrf_token: str
    created_at: float
    expires_at: float

    @property
    def user(self) -> User:
        return User(username=self.username, role=self.role)


class SessionStore:
    def __init__(self, secret: bytes, ttl_seconds: int) -> None:
        self._secret = secret
        self._ttl = ttl_seconds
        self._sessions: dict[str, Session] = {}

    def create(self, user: User) -> Session:
        now = time.time()
        session = Session(
            id=secrets.token_urlsafe(_ID_BYTES),
            username=user.username,
            role=user.role,
            csrf_token=secrets.token_urlsafe(_ID_BYTES),
            created_at=now,
            expires_at=now + self._ttl,
        )
        self._sessions[session.id] = session
        self._purge(now)
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.expires_at <= time.time():
            del self._sessions[session.id]
            return None
        return session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _purge(self, now: float) -> None:
        for session_id, session in list(self._sessions.items()):
            if session.expires_at <= now:
                del self._sessions[session_id]

    # Cookie encoding

    def sign(self, session_id: str) -> str:
        return f"{session_id}.{self._signature(session_id)}"

    def unsign(self, cookie_value: str) -> str | None:
        session_id, separator, signature = cookie_value.partition(".")
        if not separator:
            return None
        if not hmac.compare_digest(signature, self._signature(session_id)):
            return None
        return session_id

    def _signature(self, session_id: str) -> str:
        return hmac.new(
            self._secret, session_id.encode("ascii", "ignore"), sha256
        ).hexdigest()

    def resolve(self, cookie_value: str | None) -> Session | None:
        if not cookie_value:
            return None
        session_id = self.unsign(cookie_value)
        if session_id is None:
            return None
        return self.get(session_id)
