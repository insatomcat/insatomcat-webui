<!--
Copyright (C) 2026, RTE (http://www.rte-france.com)
SPDX-License-Identifier: CC-BY-4.0
-->

# Manual validation on a real machine

Point 4 of the definition of done in [AGENTS.md](../AGENTS.md). The test suite
runs against fakes, which is what makes it fast and portable, and which is
exactly why it cannot answer the questions below. Each milestone adds its
checklist here, with the result and the machine it was run on.

## M0

Nothing on this list changes the machine. If any step does, that is a bug of
the highest severity in this project.

### Prerequisites

Create the mount sources that a freshly installed machine does not have, since
podman refuses to start a container whose bind mount source is missing:

```bash
sudo mkdir -p /etc/seapath/webui /etc/seapath/inventory /var/lib/seapath-webui \
              /etc/corosync /etc/ceph /var/lib/pacemaker
```

Then install the image and the quadlet, and start it:

```bash
sudo cp seapath-webui.container /etc/containers/systemd/
sudo systemctl daemon-reload
sudo systemctl start seapath-webui
```

### Checklist

| # | Check | Why it cannot be tested against a fake | Result |
|---|---|---|---|
| 1 | The container starts on a **standalone** node, where `corosync.conf`, and possibly `/etc/ceph`, do not exist | A missing bind mount source is a podman behaviour | |
| 2 | `journalctl -u seapath-webui` shows the URL and the certificate fingerprint | The console banner is the whole trust story of the first connection | |
| 3 | The browser reaches `https://<ip_addr>:8006/` and the certificate fingerprint matches the one on the console | | |
| 3b | The certificate common name is the **node's** name, not a container id | The container's UTS namespace, which `Network=host` does not share | |
| 4 | `root` signs in with the password set by the installer | D6, and no group exists yet on a machine that never converged | |
| 5 | An account in `seapath-viewer` signs in and sees the node view; an account in no SEAPATH group is refused, naming the groups | PAM and `getgrnam` against the host's real files | |
| 6 | The node view shows the **machine's** hostname, not a container id | `/etc/hostname` mount and the UTS namespace | |
| 7 | The kernel release, distribution and uptime match `uname -r`, `/etc/os-release` and `uptime` | | |
| 8 | The isolated set matches `cat /sys/devices/system/cpu/isolated`, and the tuned profile matches `tuned-adm active` | | |
| 9 | Interface addresses match `ip addr`, and the default route interface matches `ip route` | `ip -j` output and the host network namespace | |
| 10 | Unit states match `systemctl status` for each unit listed | `systemctl` reaching the host over `/run/systemd`, which is the mount most likely to fail | |
| 11 | The journal button returns real lines for a unit that has some | `journalctl` needs `/etc/machine-id` and the journal directories | |
| 12 | The disk list shows every disk with the same `by-path` name as `ls -l /dev/disk/by-path`, the boot disk marked in use and any spare marked available | The OSD selector at M4 depends on exactly this | |
| 13 | The time card shows a PTP source and a plausible offset, or says the offset is unavailable and why | `chronyc` reaching a `timemaster` supervised chronyd is the uncertain part | |
| 14 | `systemctl show seapath-webui -p CPUAffinity` reports the housekeeping CPUs only | Real time safety | |
| 15 | `cyclictest` results on the isolated CPUs are unchanged with the service running and stopped | The service must be invisible to a real time guest | |
| 16 | After a `podman stop` and start, the certificate fingerprint is unchanged and sessions are still valid | The material must be generated once, and the session secret persisted | |
| 17 | Nothing outside `/etc/seapath/webui` was written. Compare `find /etc /var/lib -newer <marker> -not -path '/etc/seapath/*'` before and after a full browse of the UI | **The point of M0.** No writing anywhere | |

Checks 10, 11 and 13 are the ones expected to need a quadlet adjustment: they
depend on reaching host daemons through mounted sockets and directories, which
is the part no laptop can rehearse. If one of them fails, the reading must
degrade with a message naming what is missing, never fall back to a plausible
looking value.

### Result

Not yet run. Fill in the table and name the machine, the SEAPATH release and
the date.

## M1

M1 is the first milestone that changes a machine, so the checklist is mostly
about the two things a laptop cannot rehearse: SSH to the local machine, and a
playbook that reboots the host running it.

### Checklist

| # | Check | Why it cannot be tested against a fake | Result |
|---|---|---|---|
| 1 | After the first start, `/home/ansible/.ssh/authorized_keys` still holds the ISO's site key, with one line appended | The suite proves the editing; only a real ISO proves the file it starts from | |
| 2 | `ssh -i /etc/seapath/webui/ssh/id_ed25519_self ansible@<ip_addr> true` succeeds from inside the container, with no prompt | The whole self trust: the key, the `from=` restriction, and the `known_hosts` read from `/etc/ssh` | |
| 3 | The seed inventory describes this machine correctly: address, interface, prefix, gateway | Discovery against a real `ip -j addr` and a real default route | |
| 4 | Filling the form and saving produces a commit whose author is the operator, visible in `git -C /etc/seapath/inventory log` | | |
| 5 | Exporting the inventory, then running `seapath_setup_main.yaml` from a conventional Ansible control machine, reports **no change** | **The acceptance criterion that matters.** If it fails, something configured a machine behind Ansible's back | |
| 6 | A preview run (`check: true`) of `seapath_setup_main.yaml` completes and changes nothing | Check mode against real roles | |
| 7 | A real `seapath_setup_main.yaml` with "converge without rebooting" succeeds, and the node view keeps saying the machine has not rebooted | | |
| 8 | A real `seapath_setup_main.yaml` **with** the reboot ends as `interrupted`, not `failed`, and the run view offers to relaunch | The case the whole interruption design exists for, and the one no fake can produce | |
| 9 | Relaunching after that reboot succeeds and reports mostly unchanged tasks | Idempotence is the recovery story | |
| 10 | The artefacts under `/var/lib/seapath-webui/runs/<id>/` survive the reboot, event stream included | Written as the run progresses, never buffered | |
| 11 | After the reboot, the service marks the interrupted run closed and the run lock is free | A lock nobody releases is a node that can never converge again | |
| 12 | Cockpit still works after the run, meaning `deploy_cockpit_plugins` found its archives | The `build_ignore` problem: without the image's restore step this task fails and takes the run with it | |
| 13 | `GET /playbooks` marks as unavailable any entry the shipped collection does not carry, naming the collection version | Depends on what the image was built from | |
| 14 | The administration address changed through the form, then applied, leaves the self trust working after the reboot | The `from=` repair at startup | |
| 15 | `cyclictest` on the isolated CPUs is unchanged with a run in progress | A convergence must not disturb a running guest | |

Check 5 is the one that decides whether the milestone is real. Everything else
can pass while the product claim is false.

### Result

Not yet run.
