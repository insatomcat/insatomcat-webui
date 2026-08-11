# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""GRUB password hashing.

`grub_password` goes into the inventory, and the inventory goes into git, so
the value has to be a hash and never a password. The format is the one
`grub-mkpasswd-pbkdf2` produces, computed here rather than by shelling out to
it: it is plain PBKDF2-HMAC-SHA512, and depending on a `grub2-common` install
inside this container to hash a string would be a strange thing to need.
"""

from __future__ import annotations

import hashlib
import secrets

# What `grub-mkpasswd-pbkdf2 -c 65536` uses, and what the reference inventories
# were generated with.
_ROUNDS = 65536
_SALT_BYTES = 64
_KEY_BYTES = 64


def hash_password(password: str, rounds: int = _ROUNDS) -> str:
    """`grub.pbkdf2.sha512.<rounds>.<salt>.<hash>`, salt and hash in hex."""
    if not password:
        raise ValueError("The GRUB password must not be empty.")
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha512", password.encode("utf-8"), salt, rounds, dklen=_KEY_BYTES
    )
    return (
        f"grub.pbkdf2.sha512.{rounds}." f"{salt.hex().upper()}.{derived.hex().upper()}"
    )


def verify(password: str, encoded: str) -> bool:
    """Check a password against an encoded hash. Used by the tests only."""
    try:
        _, _, algorithm, rounds, salt, digest = encoded.split(".", 5)
    except ValueError:
        return False
    if algorithm != "sha512":
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha512",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        int(rounds),
        dklen=len(digest) // 2,
    )
    return secrets.compare_digest(derived.hex().upper(), digest.upper())
