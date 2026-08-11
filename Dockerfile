# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

# Python 3.11 to match what docs/deployment.md pins, and what the SEAPATH
# Debian images carry.
FROM python:3.11-slim AS builder

COPY requirements.txt .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

# The observation views read /proc and /sys directly, but three things are only
# reachable through a tool:
#   iproute2  interface addresses, which sysfs does not carry
#   systemd   unit states and the journal, over the host's /run/systemd
#   chrony    the time offset. Only the `chronyc` client is used: this image
#             never runs a time daemon, the host's timemaster owns that.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        chrony \
        iproute2 \
        libpam-modules \
        libpam0g \
        systemd \
    && rm -rf /var/lib/apt/lists/*

# M1 adds the configuration plane to this image: ansible-core ~=2.16.0, the
# seapath_ansible collection installed by the upstream prepare.sh, and an
# OpenSSH client. It is deliberately absent here, because M0 runs no playbook
# and an untested Ansible layer in the image would be dead weight carrying the
# CVEs of a dependency tree nothing uses yet.

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Reported by GET /api/v1/node, and recorded next to the inventory commit on
# every run from M1 on. A deployment is reproducible from that pair.
ARG COLLECTION_VERSION=unknown
ENV SEAPATH_WEBUI_COLLECTION_VERSION=${COLLECTION_VERSION}

COPY packaging/pam/seapath-webui /etc/pam.d/seapath-webui

WORKDIR /app
COPY app ./app

EXPOSE 8006

# Exec form so the service is PID 1 and receives the SIGTERM from `podman
# stop`. `python -m app` rather than a uvicorn command line because the TLS
# material has to exist, and its fingerprint has to reach the console, before
# the listening socket opens.
CMD ["python", "-m", "app"]
