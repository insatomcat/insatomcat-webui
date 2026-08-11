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
- the `ceph` client libraries that `vm_manager` needs in cluster mode.

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

```ini
[Unit]
Description=SEAPATH management web UI and API
After=network-online.target libvirtd.service
Wants=network-online.target

[Container]
Image=docker.io/insatomcat/seapath-webui:latest
ContainerName=seapath-webui
Network=host

# Service state: inventory repository, PKI, SSH keys, run artefacts
Volume=/etc/seapath/webui:/etc/seapath/webui:rw
Volume=/etc/seapath/inventory:/etc/seapath/inventory:rw
Volume=/var/lib/seapath-webui:/var/lib/seapath-webui:rw

# Trust material: where peer keys, and this node's own key, are installed for
# the `ansible` account. Templated by the role from the account's real home,
# never hardcoded.
Volume=/home/ansible/.ssh:/home/ansible/.ssh:rw

# Runtime plane
Volume=/var/run/libvirt/libvirt-sock:/var/run/libvirt/libvirt-sock
Volume=/etc/ceph:/etc/ceph:ro

# Read only views
Volume=/sys:/sys:ro
Volume=/run/systemd:/run/systemd:ro
Volume=/var/lib/pacemaker:/var/lib/pacemaker:ro
Volume=/etc/corosync/corosync.conf:/etc/corosync/corosync.conf:ro

# PAM authentication against local accounts
Volume=/etc/shadow:/etc/shadow:ro
Volume=/etc/passwd:/etc/passwd:ro
Volume=/etc/group:/etc/group:ro

Environment=PYTHONUNBUFFERED=1

[Service]
Restart=always
RestartSec=5
# Housekeeping CPUs only, substituted from the node's isolated set by the
# Ansible role. Never a hardcoded value.
CPUAffinity=0-1
CPUQuota=50%
Nice=5

[Install]
WantedBy=multi-user.target
```

No `--privileged`, no host podman socket, no `--pid=host`. If an implementation
finds itself needing one of those, that is the signal that it is about to
configure the host directly, which is the one thing this design forbids.

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
