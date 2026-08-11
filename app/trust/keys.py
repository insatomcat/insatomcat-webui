# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The service's SSH key pairs.

Ed25519, one pair per relation and per direction, so revoking one relation
cannot disturb another. Generated in process rather than by shelling out to
`ssh-keygen`, which keeps the key material out of a subprocess and out of any
temporary file the service does not control.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


@dataclass(frozen=True)
class KeyPair:
    private_key_file: Path
    public_key: str
    """The `ssh-ed25519 AAAA...` blob, with no comment and no options."""

    @property
    def fingerprint(self) -> str:
        """The `SHA256:...` form `ssh-keygen -l` prints, for the trust view."""
        blob = base64.b64decode(self.public_key.split()[1])
        digest = base64.b64encode(sha256(blob).digest()).decode("ascii")
        return "SHA256:" + digest.rstrip("=")


def ensure_key_pair(directory: Path, name: str) -> KeyPair:
    """Load the pair, generating it on first use.

    Never regenerates: the public key is installed in an `authorized_keys` this
    service does not own the only copy of, and a new key pair would leave the
    old line behind, authorising nothing and explaining nothing.
    """
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    private_key_file = directory / name
    public_key_file = directory / f"{name}.pub"

    if not private_key_file.exists():
        key = ed25519.Ed25519PrivateKey.generate()
        _write_private(
            private_key_file,
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption(),
            ),
        )
        public_key_file.write_bytes(
            key.public_key().public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH,
            )
            + b"\n"
        )

    return KeyPair(
        private_key_file=private_key_file,
        public_key=public_key_file.read_text().strip(),
    )


def _write_private(path: Path, payload: bytes) -> None:
    """Create the file with its final mode, never wider for a moment."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
    os.chmod(path, 0o600)
