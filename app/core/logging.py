# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Logging setup.

The service logs to stdout, which the quadlet hands to the journal. Two audit
events are emitted on a dedicated logger, `seapath.audit`, so a site can route
them separately: who authenticated, and who launched what. From M1 the
inventory commits and the runs join them.
"""

import logging
import sys
from typing import Any

audit = logging.getLogger("seapath.audit")


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # uvicorn installs its own handlers, which would duplicate every line.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def audit_event(event: str, **fields: Any) -> None:
    """Record an operator action.

    Never pass a secret here. Passwords, tokens and the corosync authkey have
    no business in the journal, and the authkey never reaches this service at
    all.
    """
    rendered = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
    audit.info("%s %s", event, rendered)
