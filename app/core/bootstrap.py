# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""What happens at every start, and what happened only at the first one.

None of this is guarded by an "is this the first boot" flag. Each step is
idempotent and is run every time, which is what makes them repairs rather than
one shot initialisations: re-provisioning the self trust is how the relation
survives an administration address change, and re-reading the host keys is how
`known_hosts` survives a host key rotation.

Nothing here is allowed to stop the service from starting. A node that cannot
provision its trust must still serve its UI, because the operator's next move
is to look at the UI and find out why.
"""

from __future__ import annotations

import logging

from app.hosts.reader import HostReader
from app.inventory.service import InventoryService
from app.runs.service import RunService
from app.trust import known_hosts
from app.trust.authorized_keys import MissingAccount
from app.trust.service import TrustService

logger = logging.getLogger(__name__)


def node_addresses(reader: HostReader) -> list[str]:
    """The addresses a connection from this node would arrive from.

    Used for the `from=` restriction on the installed key. Only the interface
    carrying the default route is taken: adding every address on the machine
    would turn a restriction into a formality.
    """
    network = reader.network()
    return [
        address.address
        for interface in network.interfaces
        if interface.name == network.default_route_interface
        for address in interface.addresses
        if address.family == "inet"
    ]


def run_startup_tasks(
    hostname: str,
    reader: HostReader,
    trust: TrustService,
    inventory: InventoryService,
    runs: RunService,
    settings,
) -> None:
    addresses = node_addresses(reader)

    try:
        _, changed = trust.ensure_self_trust(hostname, addresses)
        if changed:
            logger.info("The self trust relation was provisioned or repaired")
    except MissingAccount as error:
        # The service does not create the account. A machine where it is
        # missing was not installed from the SEAPATH ISO, and inventing a user
        # with privileges nobody reviewed is a second problem, not a recovery.
        logger.error(
            "Could not provision the self trust, so this node cannot converge "
            "anything: %s",
            error,
        )
    except OSError as error:
        logger.error("Could not provision the self trust: %s", error)

    try:
        known_hosts.ensure_local(
            settings.known_hosts_file,
            settings.ssh_config_dir,
            [hostname, *addresses, "127.0.0.1", "localhost"],
        )
    except OSError as error:
        logger.error("Could not record the local host keys: %s", error)

    try:
        inventory.ensure_seed()
    except Exception as error:  # pragma: no cover - defensive
        logger.error("Could not write the seed inventory: %s", error)

    # A record left saying `running` is a run whose process is gone, because
    # the machine rebooted or the container restarted. Leaving it would hold
    # the run lock forever and block every future convergence.
    for record in runs.reconcile():
        logger.warning(
            "Run %s was going when the service stopped, and is relaunchable",
            record.id,
        )
