<!--
Copyright (C) 2026, RTE (http://www.rte-france.com)
SPDX-License-Identifier: CC-BY-4.0
-->

# seapath-webui

A management UI and REST API running on every SEAPATH node, so that a machine
installed from the ISO is usable from a browser, several machines can be joined
into a cluster, and Ceph can be deployed on top, with no separate Ansible
control machine.

**It does not configure machines. It edits the inventory and runs the SEAPATH
playbooks.** SEAPATH is a function converting an inventory into a running
infrastructure, and this service is a friendly front end onto that function, not
a way around it. The fourth machine disappears as a machine, not as a function:
its two jobs, holding the desired state and running the playbooks, move into the
cluster itself.

Concretely, the service does four things:

1. holds the inventory in a git repository replicated across the nodes, and
   edits it through guided forms seeded by hardware discovery;
2. brokers SSH trust between nodes, bootstrapped by a manual secret exchange in
   the Proxmox style, so any node can drive the others;
3. runs the upstream playbooks with `ansible-runner` and turns their event
   stream into a readable progress view;
4. exposes the runtime plane, meaning starting, stopping and migrating VMs,
   which is not configuration and does not belong in an inventory.

No SEAPATH role is rewritten, and no configuration file is rendered twice. What
the UI runs is what the CI tests.

## Status

Specification only. No code yet.

1. [SPEC.md](SPEC.md) - principle, scope, architecture, milestones, risks.
2. [docs/inventory.md](docs/inventory.md) - the desired state: storage, writers,
   discovery, and the form to variable mapping. The heart of the product.
3. [docs/cluster-join.md](docs/cluster-join.md) - trust between nodes and
   cluster formation.
4. [docs/playbooks.md](docs/playbooks.md) - which playbooks the UI exposes, and
   what to warn about before each one.
5. [docs/api.md](docs/api.md) - REST API surface.
6. [docs/ceph.md](docs/ceph.md) - the Ceph flow, which is mostly a disk
   selector and a playbook.
7. [docs/deployment.md](docs/deployment.md) - image, quadlet, Ansible role, ISO.
8. [docs/decisions.md](docs/decisions.md) - settled decisions with their
   reasoning, and the open ones with a recommendation.
9. [AGENTS.md](AGENTS.md) - conventions and definition of done.

## Related components

| Component | Repository | Relation |
|---|---|---|
| `seapath-ansible` | `~/dev/seapath-ansible` | The collection this service ships and runs. Roles are used unchanged. |
| `vm_manager` | `~/dev/vm_manager` | Python library for the runtime plane. Consumed, not reimplemented. |
| `vmmgrapi` role | `seapath-ansible/roles/vmmgrapi` | The existing thin API over `vm_manager`. Deprecated at M5. |
| `rtperfui` | `~/dev/rtperfui` | Packaging precedent: FastAPI, Jinja, quadlet with host mounts. |
| `insatomcat-exporter` | `~/dev/insatomcat-exporter` | Precedent for the image build and publish flow. |
