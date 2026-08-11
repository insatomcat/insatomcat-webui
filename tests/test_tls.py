# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""First boot TLS material."""

from __future__ import annotations

import ipaddress
import stat

from cryptography import x509

from app.core.settings import Settings
from app.core.tls import ensure_session_secret, ensure_tls_material


def test_the_certificate_is_generated_on_the_first_call(settings: Settings) -> None:
    material = ensure_tls_material(settings, hostname="node1")

    assert settings.tls_cert_file.exists()
    assert material.fingerprint.startswith("SHA256:")
    # 32 bytes rendered as colon separated hexadecimal.
    assert len(material.fingerprint.split(":")) == 33


def test_the_certificate_is_never_regenerated(settings: Settings) -> None:
    first = ensure_tls_material(settings, hostname="node1")
    second = ensure_tls_material(settings, hostname="node1")

    # A joining node pins this fingerprint, so silently rotating it would
    # break every trust relation already established.
    assert first.fingerprint == second.fingerprint


def test_the_private_key_is_not_readable_by_anyone_else(settings: Settings) -> None:
    ensure_tls_material(settings, hostname="node1")

    mode = stat.S_IMODE(settings.tls_key_file.stat().st_mode)

    assert mode == 0o600


def test_the_addresses_from_the_inventory_become_subject_alternative_names(
    settings: Settings,
) -> None:
    settings = settings.model_copy(
        update={"tls_additional_sans": "192.168.200.121,192.168.55.1"}
    )

    ensure_tls_material(settings, hostname="node1")
    certificate = x509.load_pem_x509_certificate(settings.tls_cert_file.read_bytes())
    names = certificate.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    ).value

    assert "node1" in names.get_values_for_type(x509.DNSName)
    addresses = names.get_values_for_type(x509.IPAddress)
    assert ipaddress.ip_address("192.168.200.121") in addresses
    assert ipaddress.ip_address("192.168.55.1") in addresses


def test_the_session_secret_is_generated_once_and_kept(settings: Settings) -> None:
    first = ensure_session_secret(settings)
    second = ensure_session_secret(settings)

    assert first == second
    assert len(first) == 64
    assert stat.S_IMODE(settings.session_secret_file.stat().st_mode) == 0o600
