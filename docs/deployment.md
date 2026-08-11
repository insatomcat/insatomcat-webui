<!--
Copyright (C) 2026, RTE (http://www.rte-france.com)
SPDX-License-Identifier: CC-BY-4.0
-->

# Packaging and deployment

## 1. Image

Multi stage `Dockerfile`, same shape as `insatomcat-exporter`. Published as
`docker.io/insatomcat/seapath-webui`, built and pushed by `buildpush.sh`.

Contents:

- Python 3.11, FastAPI, uvicorn, Jinja2, `ansible-runner`;
- `ansible-core` pinned to `~=2.16.0`, which `prepare.sh` enforces in
  `seapath-ansible` and which this image must match;
- the `seapath_ansible` collection with its galaxy dependencies and its
  submodules, installed at build time by running the upstream `prepare.sh`;
- an OpenSSH client;
- `libvirt0` and the `vm_manager` package, for the runtime plane;
- the `ceph` client libraries that `vm_manager` needs in cluster mode;
- `iproute2`, `systemd` and the `chronyc` client, which is what the three
  readings that are not in `/proc` or `/sys` need: interface addresses, unit
  states and the journal, and the time offset. The image never runs a time
  daemon: `timemaster` on the host owns that.

Each layer arrives with the milestone that uses it, so that the image never
carries the dependency tree, or the CVEs, of something no code calls yet. M0
ships the service and the reading tools. The Ansible layer, meaning
`ansible-core`, the collection, `git` and the OpenSSH client, arrives at M1 with
the run adapter. The runtime layer, `libvirt0`, `vm_manager` and the Ceph client
libraries, arrives at M2.

`git` is not incidental: the inventory repository is the configuration audit
trail, and the service shells out to `git` for every commit, diff and revert.

### Building the collection into the image

A dedicated stage clones `seapath-ansible` and runs its own `prepare.sh`. No
role is patched. Two things about that build are worth knowing, and both were
found by running it rather than by reading it:

- `prepare.sh` installs the local collection **before** it updates the git
  submodules, so the copy it installs carries an empty
  `roles/deploy_cukinia/files/cukinia`. The image installs the collection a
  second time, afterwards.
- `build_ignore` in `galaxy.yml` is matched against whole relative paths, so
  `"*.tar.gz"` strips `roles/deploy_cockpit_plugins/files/*.tar.gz`. Those two
  archives are what `deploy_cockpit_plugins` unarchives, and
  `seapath_setup_main.yaml` imports that role on every distribution except
  Yocto. Without them the commissioning run fails on any machine that has
  Cockpit, which is every machine installed from the SEAPATH ISO. The image
  restores the two files after installing the collection. See
  [playbooks.md](playbooks.md).

The collection version is stamped into the image with `--build-arg
COLLECTION_VERSION`, reported by `GET /api/v1/node`, and recorded on every run
next to the inventory commit. That pair is what makes a deployment
reproducible, and the catalogue refuses to offer an entry the shipped
collection does not contain.

The collection version is part of the image identity. It determines which
playbooks exist and what they do, so it is recorded at build time, reported by
`/api/v1/node`, and shown in the run view next to the inventory commit. A run
is identified by the pair "inventory commit, collection version", and that pair
is what makes a deployment reproducible.

The image must therefore be released in step with SEAPATH. An image carrying a
collection newer than the machines is how a playbook meets a host it was not
written for.

## 2. Quadlet

`seapath-webui.container`, installed to `/etc/containers/systemd/`.

Note how much smaller the host surface is than in a design where the service
configures the machine itself. The configuration plane goes out over SSH, even
to the local node, so no host **configuration** is written from here. Exactly
two host paths are mounted writable: the service's own state, and the
`authorized_keys` of the `ansible` account, which is the trust material. Every
other mount serves the runtime plane or a read only view.

The file itself is [`seapath-webui.container`](../seapath-webui.container) at the
root of the repository, kept there rather than copied here so the two cannot
drift apart.

No `--privileged`, no host podman socket, no `--pid=host`. If an implementation
finds itself needing one of those, that is the signal that it is about to
configure the host directly, which is the one thing this design forbids.

### What the node view actually needs, and what that changed

Writing the read only adapter turned up four mounts the first draft of this
document was missing, and one that would have stopped the container from
starting.

- **`/etc/corosync`, the directory, not `corosync.conf`.** That file only
  appears once `cluster_setup_ha.yaml` has run. Bind mounting a source that
  does not exist keeps the container from starting, so the original line would
  have broken every standalone node, which is exactly the machine M1 targets.
- **`/etc/hostname`, `/etc/os-release`, `/etc/machine-id`.** The container has
  its own UTS namespace, so without the first the node view would show a
  container id where the machine's name belongs. `machine-id` is how
  `journalctl` finds the right journal directory.
- **`/etc/tuned` and `/run/tuned`.** The active profile is an RT relevant fact
  and it lives there.
- **`/dev/disk`.** The stable `by-path` names are symlinks created by udev, and
  `ceph_osd_disks` is written in that form. Only the symlink directory is
  mounted, not the device tree.
- **`/var/log/journal` and `/run/log/journal`,** for the journal tail.
- **`/etc/ssh`, read only,** added at M1. It carries the machine's public SSH
  host keys, and reading them off the filesystem is how the first SSH
  connection is verified without either prompting, which hangs a run forever,
  or `StrictHostKeyChecking=no`, which is a real man in the middle window on
  the administration network. No network is involved, so there is nothing to
  intercept. See [cluster-join.md](cluster-join.md).

`/proc` is deliberately **not** mounted. `uptime`, `cpuinfo`, `cmdline` and
`stat` are not namespaced, and with the host network namespace neither is
`/proc/net`, so the container's own `/proc` already reports the host's values.

Three mounts name paths that do not exist on a freshly installed machine:
`/etc/ceph`, `/var/lib/pacemaker` and `/etc/corosync`. The role, and the ISO
first boot unit before it, must create them empty. A missing source is a
container that does not start, and a node that does not answer its browser is
the one failure this whole project exists to prevent.

## 3. Surviving the runs it launches

A playbook can reboot the machine running it, and
`seapath_setup_hardening.yaml` does exactly that, on every host. The network
roles can also cut the connection. So a run will die mid flight, and the design
answer is not to prevent it but to make it harmless:

- artefacts are written to `/var/lib/seapath-webui/runs/<id>/` as the run
  progresses, never buffered in memory, so the trace survives;
- a run that ends without a final status is marked `interrupted`, not `failed`,
  and the view offers to relaunch it;
- relaunching is safe because the playbooks are idempotent, which is the whole
  point of converging rather than mutating;
- playbooks that reboot are flagged in `GET /playbooks` and the UI warns before
  launching one from the machine it will reboot, suggesting the operator drive
  it from another node instead.

Running the Ansible process in a sibling container, so that it survives a
restart of the service itself, is a possible hardening. It costs access to the
podman socket, which is root on the host, and buys little given that the
interruptions that matter are reboots. Left as D9, deliberately unimplemented.

## 4. Ansible role

`seapath-ansible/roles/deploy_seapath_webui`, following the `deploy_*`
conventions.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `seapath_webui_enabled` | no | `true` | Deploy and enable |
| `seapath_webui_image` | no | `docker.io/insatomcat/seapath-webui:latest` | Image reference |
| `seapath_webui_bind_address` | no | `{{ ip_addr }}` | Listen address, administration network |
| `seapath_webui_port` | no | `8006` | Listen port |
| `seapath_webui_admin_group` | no | `seapath-admin` | Unix group granting the admin role |
| `seapath_webui_cpu_affinity` | no | computed from `isolcpus` | Housekeeping CPUs |
| `seapath_webui_ansible_user` | no | `{{ ansible_user }}` | The account the trust targets, must match the inventory |
| `seapath_webui_ansible_user_home` | no | looked up with `getent` | Source of the `.ssh` mount, never hardcoded to `/home/ansible` |

Tasks: create the state directories, initialise the inventory repository if
absent, create the three Unix groups, template the quadlet, `daemon-reload`,
enable and start. Strictly idempotent, with a handler restarting only the
service and only when the quadlet or the configuration changed.

The role has a pleasing property: it deploys the tool that runs the role. A
site can bootstrap from a fourth machine, then let the cluster take over, or the
other way round.

## 5. ISO integration

The ISO ships the image and the quadlet so a fresh machine serves the UI on
first boot with no network fetch. First boot must:

1. generate the TLS certificate and the session secret;
2. provision the **self trust**: an SSH key pair for the service, installed in
   the `ansible` account of this same machine, without which the service cannot
   converge even a standalone node, since the inventory sets
   `ansible_connection: ssh` for every host including the local one;
3. run hardware discovery and write the seed inventory;
4. print the URL and the certificate fingerprint on the console, because the
   whole trust exchange depends on the operator being able to verify it;
5. ensure one account can log in, per D6.

The ISO already provides what step 2 needs, verified in
`seapath-build_debian_iso`: the `ansible` account with sudo, and
`/home/ansible/.ssh/authorized_keys` seeded with the site key at build time. The
service appends its own line to that file and never rewrites it, because the
site key is how a conventional Ansible control machine reaches the node.

## 6. Migration from vmmgrapi

`roles/vmmgrapi` exposes four `vm_manager` endpoints through gunicorn and nginx.
At M5 its README gains a deprecation notice, the ISO stops enabling it, and
`enable_vmmgr_http_api` stays default false so nothing breaks. The ports differ,
so both can run side by side for at least one release. The role is not deleted:
someone has automation against those endpoints.
