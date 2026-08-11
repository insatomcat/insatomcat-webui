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
