# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Turning the model into the YAML Ansible reads.

Rendered through PyYAML rather than a template. A template would produce a
prettier file with inline comments, and would also happily emit invalid YAML
the day an operator types a colon into a field. The inventory is the desired
state of a substation hypervisor: it is worth more correct than pretty, and the
explanations live in the UI.

The fixed values below are not decisions an operator gets to make. They are
what makes a generated inventory equivalent to a hand written one, which is the
claim the whole design rests on.
"""

from __future__ import annotations

from typing import Any

import yaml

from app.inventory.model import Inventory, Mode, NodeConfig

_HEADER = """\
# SEAPATH inventory, managed by seapath-webui.
#
# This file is the desired state of the machines below. It is a plain Ansible
# inventory: clone this repository onto a conventional control machine and the
# same playbooks produce the same result.
#
# Every change is a commit whose author is the operator who made it, so
# `git log` is the configuration audit trail.
#
# The service rewrites this file on every change. Variables it does not model
# are read back and written out untouched, but the layout and the comments are
# not: edit through the UI, or edit here and expect the next commit to reformat
# what you wrote.
"""

# Written for every host, on every render.
#
# `hostname` matters more than it looks: `network_buildhosts` sets the
# machine's name from `hostname | default(inventory_hostname)`, so the host key
# in this file is what the machine ends up called. The standalone example omits
# the variable and relies on the default, which is equivalent, and writing it
# explicitly is what the cluster example does.
#
# `apply_network_config` matters just as much: `seapath_setup_network.yaml`
# defaults it to false, so an inventory that leaves it out configures no
# network at all.
FIXED_HOST_VARS: dict[str, Any] = {
    "hostname": "{{ inventory_hostname }}",
    "ip_addr": "{{ ansible_host }}",
    "apply_network_config": True,
    "ansible_connection": "ssh",
    "ansible_python_interpreter": "/usr/bin/python3",
    "ansible_remote_tmp": "/tmp/.ansible/tmp",
    "ansible_user": "ansible",
}

# The PTP domain propagates to the timemaster and vsock variables. The cluster
# example ties them together exactly like this.
PTP_DOMAIN_ALIASES = (
    "timemaster_ptp_domain_number",
    "ptp_status_vsock_domain_number",
)


def render(inventory: Inventory) -> str:
    """The inventory as YAML, deterministic for a given model."""
    document: dict[str, Any] = {"all": {"hosts": _hosts(inventory)}}

    if inventory.mode is Mode.STANDALONE:
        names = inventory.host_names()
        document["standalone_machine"] = {"hosts": _host_set(names)}
        document["hypervisors"] = _group_with_isolcpus(inventory, names)
        # Empty groups, to prevent the warnings the reference inventory
        # prevents the same way.
        document["cluster_machines"] = None
        document["observers"] = None
    else:  # pragma: no cover - cluster arrives at M3
        raise NotImplementedError("Cluster inventories are rendered from M3.")

    body = yaml.dump(
        document,
        Dumper=_IndentedDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=1000,
    )
    return f"{_HEADER}---\n{body}"


class _IndentedDumper(yaml.SafeDumper):
    """Indent list items under their key, the way a person would write them.

    PyYAML puts sequence items at the indentation of the key by default, which
    is valid YAML and looks wrong next to the reference inventories. This file
    is meant to be read, cloned and edited by people.
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def _hosts(inventory: Inventory) -> dict[str, Any]:
    return {name: _host_vars(node) for name, node in inventory.hosts.items()}


def _host_vars(node: NodeConfig) -> dict[str, Any]:
    variables: dict[str, Any] = {
        "ansible_host": node.ansible_host,
        "network_interface": node.network_interface,
        "subnet": node.subnet,
    }
    if node.gateway_addr:
        variables["gateway_addr"] = node.gateway_addr
    if node.dns_servers:
        # The role documents a list, and its template joins a list or passes a
        # string through, so the two forms are equivalent.
        variables["dns_servers"] = list(node.dns_servers)

    # An observer receives no sampled values and has no PTP interface, which is
    # exactly what the cluster example says to remove when converting one.
    if node.ptp_interface:
        variables["ptp_interface"] = node.ptp_interface
    if node.ptp_domain_number is not None:
        variables["ptp_domain_number"] = node.ptp_domain_number
        for alias in PTP_DOMAIN_ALIASES:
            variables[alias] = "{{ ptp_domain_number }}"
    if node.ntp_servers:
        variables["ntp_servers"] = list(node.ntp_servers)

    if node.admin_user:
        variables["admin_user"] = node.admin_user
    if node.grub_password:
        variables["grub_password"] = node.grub_password

    # Variables this service does not model, preserved exactly as they were
    # read. They come before the fixed values so a hand written override of a
    # fixed value cannot quietly win: those are what make the file equivalent
    # to the reference inventory.
    variables.update(node.extra)
    variables.update(FIXED_HOST_VARS)
    return variables


def _host_set(names: list[str]) -> dict[str, Any]:
    return {name: None for name in names}


def _group_with_isolcpus(inventory: Inventory, names: list[str]) -> dict[str, Any]:
    group: dict[str, Any] = {"hosts": _host_set(inventory.hypervisors() or names)}
    # The reference inventory carries isolcpus as a group variable, because it
    # is a property of a fleet of identical machines rather than of one.
    isolated = {
        node.isolcpus
        for name, node in inventory.hosts.items()
        if name in names and node.isolcpus
    }
    if len(isolated) == 1:
        group["vars"] = {"isolcpus": isolated.pop()}
    return group


# The names the renderer always writes itself, so the parser can tell them from
# a variable a site added by hand.
FIXED_HOST_VAR_NAMES = frozenset(FIXED_HOST_VARS)
