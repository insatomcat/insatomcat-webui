<!--
Copyright (C) 2026, RTE (http://www.rte-france.com)
SPDX-License-Identifier: CC-BY-4.0
-->

# Exposed playbooks

The UI runs whole playbooks, never a free form selection of tags. This document
is the catalogue behind `GET /api/v1/playbooks`, and adding an entry to it is a
deliberate act, not a consequence of a playbook existing upstream.

## 1. Why whole playbooks

The tags in `seapath-ansible` were not designed as a public interface, and
`ansible.cfg` already skips `package-install` by default. A tag selector looks
flexible and produces combinations nobody has ever run. A whole playbook is what
the CI executes, so it is the only granularity with evidence behind it.

Scoping comes later, as a small curated set of named operations, if and only if
an operational need is proven. When that happens, each scoped operation gets its
own catalogue entry with its own tags baked in, and never a tag field in the UI.

## 2. Attributes of an entry

Each entry carries what the UI needs to present the run honestly:

| Attribute | Meaning |
|---|---|
| `targets` | Inventory groups the playbook plays against |
| `preview` | `full`, `partial` or `none`, see section 3 |
| `reboots` | Whether the playbook reboots its targets, and whether that is gated by a variable |
| `disruption` | What an operator should expect on a live machine |
| `requires` | Preconditions checked before the run is offered |
| `variables` | The only variables `POST /runs` accepts for this playbook, each with a type and a validation rule. Empty for most entries |

The `targets` attribute is copied from the playbook's own `hosts:` lines and is
not a parameter the caller can override. A caller cannot narrow a run to one
node: Ansible would accept it and the result would be meaningless, since
`cluster_setup_ha.yaml` on a single member of three is not a smaller version of
forming a cluster.

## 3. Preview quality

Check mode is honest only where roles write files through `template`, `copy` and
`lineinfile`. Roles built on `command` and `shell`, which is most of
`configure_ha` and `cephadm`, are skipped or report a meaningless change. The
attribute is therefore per playbook, and the UI never renders a `partial` or
`none` check as a guarantee. A `none` playbook offers no preview button at all,
rather than a button that lies.

## 4. Catalogue, first version

### Machine configuration

| Playbook | Targets | Preview | Reboots | Notes |
|---|---|---|---|---|
| `seapath_setup_main.yaml` | `cluster_machines`, `standalone_machine`, `VMs` | partial | yes, gated by `skip_reboot_setup` | The full convergence. Imports prerequisites, network, timemaster, libvirt, snmp, exporters, the cluster playbooks and `deploy_seapath_alloc`. This is the commissioning path and what the CI runs. |
| `seapath_setup_network.yaml` | `cluster_machines`, `standalone_machine` | partial | yes | Applies only when `apply_network_config` is true. The playbook most likely to cut the connection under the run. Warn hard when launched from a target machine. |
| `seapath_setup_timemaster.yaml` | `cluster_machines`, `standalone_machine` | full | no | PTP and NTP, plus `ptp_status_vsock` unless `disable_vsock`. |
| `seapath_setup_libvirt.yaml` | `hypervisors` | partial | no | |
| `seapath_setup_prometheus_exporters.yaml` | `cluster_machines`, `standalone_machine` | full | no | |
| `seapath_setup_snmp.yaml` | `cluster_machines`, `standalone_machine` | full | no | |
| `seapath_setup_deploy_seapath_alloc.yaml` | `hypervisors` | partial | no | Dynamic CPU pinning. RT relevant, confirmation names the impacted machines. |
| `seapath_setup_hardening.yaml` | `cluster_machines`, `standalone_machine`, `VMs` | partial | yes | Ends with a reboot of every host. Sets `PermitRootLogin no` and restricts `ListenAddress`, which is why the trust targets the `ansible` account. Offered only after the rest converges cleanly. |

### Cluster

| Playbook | Targets | Preview | Reboots | Notes |
|---|---|---|---|---|
| `cluster_setup_ha.yaml` | `cluster_machines` | none | no | Corosync, the authkey, Pacemaker, stonith disabled. Command driven, so no preview. |
| `cluster_setup_cephadm.yaml` | `cluster_machines` | none | no | Bootstrap, monitors, OSDs. Destructive on the selected disks. The inventory diff is the review step, since check mode cannot be one. |
| `cluster_setup_libvirt.yaml` | `hypervisors:&cluster_machines` | full | no | RBD secret for libvirt. |
| `cluster_setup_users.yaml` | `hypervisors:&cluster_machines` | full | no | The `libvirtadmin` user, needed for live migration and console access. |
| `cluster_remove_machine.yaml` | `cluster_machines` | none | no | Requires `machine_to_remove`. Must run from a surviving node. |

### VMs

| Playbook | Targets | Preview | Reboots | Notes |
|---|---|---|---|---|
| `deploy_vms_cluster.yaml` | first host of `cluster_machines` | partial | no | Deploys every VM in the `VMs` group. Note it already runs from one node, so which node drives is irrelevant. |
| `deploy_vms_standalone.yaml` | `standalone_machine` | partial | no | |

### Not exposed in the first version

- `seapath_update_debian.yaml` and the Yocto update playbooks. They snapshot the
  root LVM, temporarily disable the GRUB password, arm a boot counter and
  reboot. That sequence deserves its own screen with its own rollback story, not
  a line in a generic run list.
- `seapath_revert_hardening.yaml`. Reachable from a console, not from a browser.
- `ci_*.yaml`, `test_*.yaml`. CI and test helpers, no operational meaning here.
- `seapath_setup_vmmgrapi.yaml`. Deprecated by this service.
- `seapath_setup_custom_hardware.yaml`, `seapath_setup_configure_nic_irq_affinity.yaml`.
  Site specific, driven by variables the UI does not model yet.

## 5. The reboot question

`seapath_setup_main.yaml` reboots at the end unless `skip_reboot_setup` is set.
On a substation, a reboot is scheduled, not improvised, so the UI asks before
launching:

- **reboot now**, the default at commissioning, when nothing runs yet;
- **converge without rebooting**, which sets `skip_reboot_setup` and tells the
  operator plainly that the configuration is not fully applied until a reboot
  happens, and keeps that state visible in the node view.

Never silently set `skip_reboot_setup`. A machine that believes it is converged
and is not is worse than one that rebooted at an inconvenient time.

## 6. Ordering

The UI does not invent an orchestration engine. `seapath_setup_main.yaml`
already imports the right playbooks in the right order, and it is the entry
point for commissioning. The individual entries exist for day two, when an
operator changes one thing and wants to converge that thing, and the UI states
which playbook covers which part of the inventory so the choice is obvious from
the form the operator just edited.

When a run fails, the UI does not chain into the next playbook. `any_errors_fatal`
means the cluster is in a partial state, and the operator decides what happens
next.
