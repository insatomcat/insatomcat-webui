<!--
Copyright (C) 2026, RTE (http://www.rte-france.com)
SPDX-License-Identifier: CC-BY-4.0
-->

# Decisions

Settled decisions are recorded with their reasoning, because the reasoning is
what a later reader needs in order to know whether the decision still holds.
Open ones carry a recommendation so implementation is never blocked.

## D1 - Settled: the UI edits the inventory, it does not configure machines

**The structural decision of the project.** Three candidates were weighed:

- **A. Reimplement the logic** in Python, writing `corosync.conf` and running
  `cephadm` directly, coordinating nodes over an mTLS channel between the
  services.
- **B. Pull convergence,** each node running Ansible against `localhost` from a
  shared inventory, with the services orchestrating the ordering.
- **C. Push convergence,** a manual secret exchange establishing SSH trust
  between nodes, after which any node runs the existing playbooks against the
  others.

**C is chosen.** A destroys the property that defines SEAPATH: the product is a
function from an inventory to an infrastructure, and a UI that mutates machines
imperatively is no longer that product. It also duplicates the most dangerous
logic in the codebase, cluster formation and OSD handling, into a second
implementation that CI does not test.

B preserves the paradigm but requires making `configure_ha` and `cephadm`
mono-host, since both are multi-host by construction through `delegate_to`,
`add_host` and a `fetch` of the corosync authkey through the control machine.
That means rewriting tested code on the most dangerous path, for the sole
benefit of avoiding SSH between nodes.

C keeps every role untouched, keeps the CI tested execution paths, and pays for
it with an SSH mesh whose trust is established by an explicit operator gesture.
The three machines already share a corosync secret, a Ceph cluster and each
other's VM storage, so the mesh makes an existing trust domain explicit rather
than creating a new one.

## D2 - Settled: the trust targets the `ansible` account, permanently, restricted

Root SSH is not an option: `configure_hardening` sets `PermitRootLogin no`,
`PasswordAuthentication no` and `AuthenticationMethods publickey`, so a root
based trust breaks on the first hardened machine. The target is the `ansible`
account with sudo, which the reference inventories already assume.

The trust is permanent rather than armed per run. Ephemeral trust sounds safer,
but every day two operation goes through a playbook, so it would be re-armed
constantly, and a cleanup that fails leaves exactly the state it was meant to
avoid. Permanent and visible beats ephemeral and unreliable.

Restriction means `from=` bound to the peer's administration and cluster
addresses, `restrict` with `pty` added back for sudo, one key pair per
direction, and revocation from the UI. It does not mean a command restriction,
because Ansible needs arbitrary root and pretending otherwise would be theatre.
Say so in the security documentation rather than implying a limit that is not
there.

## D3 - Settled: the inventory is a git repository replicated across nodes

Single writer under quorum, the commit hash as the version of the desired
state, `git log` as the audit trail, `git revert` as the rollback, and export
as a tarball for a site that wants a conventional control machine.

Rejected alternatives: plain files synchronised by the service, which loses
history and still has to solve concurrent edits; and an external git remote,
which is the most orthodox infrastructure as code answer but makes an offline
commissioning impossible, and commissioning is precisely when a substation is
least connected.

## D4 - Settled: three nodes

Not an arbitrary limit. The reference cluster inventory encodes a physical ring:
`team0_0` and `team0_1` are the two cluster interfaces, `cluster_next_ip_addr`
and `cluster_previous_ip_addr` name the neighbours, and `br_rstp_priority`
breaks the loop. `/etc/cluster.conf` also has room for exactly three entries and
`vm_manager` reads `observer` from it. A fourth node is a topology question, not
a form field. Two hypervisors plus one observer, or three hypervisors, covers
the target deployment.

## D5 - Open: VM console

A serial or VNC console is what makes a UI feel complete, and it is also a
websocket proxy into a guest.

**Recommendation: out of scope until M5.** Then reconsider, starting with the
serial console for `operator` and above, proxied through the owning node, bound
to the authenticated session, with a hard timeout.

## D6 - Open: first login credentials

The ISO must produce a machine reachable from a browser immediately, with no
prior Ansible run.

**Recommendation: accept `root` through PAM** with the installer requiring a
root password. It is the Proxmox behaviour and needs no new machinery. Note the
interaction with D2: this is local PAM authentication to the web service, not
SSH, so `PermitRootLogin no` does not affect it. If hardening later forbids
even that, fall back to a one time token printed on the console at first boot.

## D7 - Open: where this repository ends up

The service manages SEAPATH machines and ships the SEAPATH collection. It may
belong under the SEAPATH organisation rather than as a personal project.

**Recommendation:** develop here, keep Apache-2.0 and SPDX discipline from day
one so upstreaming is a move rather than a relicensing, and raise it with the
maintainers once M1 is demonstrable.

## D8 - Settled: whole playbooks, scoping later if the need is proven

A full `seapath_setup_main.yaml` on a live cluster restarts a lot, so scoping by
tags is tempting. It is refused for now: the tags in `seapath-ansible` were
never designed as a public interface, `ansible.cfg` already skips
`package-install` by default, and a tag selector produces combinations nobody
has run. A whole playbook is what the CI executes, which makes it the only
granularity with evidence behind it.

If scoping proves necessary, each scoped operation becomes its own catalogue
entry with its tags baked in. A free form tag field never appears in the UI.

The catalogue is [playbooks.md](playbooks.md), and it is deliberately smaller
than the list of playbooks in the repository.

## D9 - Open: run the Ansible process in a sibling container

Would let a run survive a restart of the service itself, at the cost of access
to the podman socket, which is root on the host.

**Recommendation: do not.** The interruptions that matter are reboots and
network changes, which a sibling container does not survive either. Persisted
artefacts plus idempotent relaunch cover the need. Revisit only if operators
report losing runs for reasons other than a reboot.
