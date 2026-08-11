# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Entry point.

The TLS material has to exist before uvicorn opens its socket, and its
fingerprint has to reach the console before the operator is asked to trust it.
That ordering is why the service starts uvicorn itself instead of being handed
to a `uvicorn app.main:app` command line.
"""

import uvicorn

from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.core.tls import ensure_tls_material, print_console_banner
from app.hosts.local import read_hostname
from app.main import create_app


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    # The node's name, not this container's: the certificate names the machine
    # an operator is about to trust.
    tls = ensure_tls_material(settings, hostname=read_hostname(settings.host_root))
    host = settings.bind_address if settings.bind_address != "0.0.0.0" else None
    print_console_banner(
        f"https://{host or '<node address>'}:{settings.port}/", tls.fingerprint
    )

    uvicorn.run(
        create_app(settings),
        host=settings.bind_address,
        port=settings.port,
        ssl_certfile=str(tls.cert_file),
        ssl_keyfile=str(tls.key_file),
        log_config=None,
        # Real time safety: the service shares the housekeeping CPUs with
        # everything else the node has to do, so it stays single process.
        workers=None,
    )


if __name__ == "__main__":
    main()
