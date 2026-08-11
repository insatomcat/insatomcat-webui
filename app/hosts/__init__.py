# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Host access, confined to adapters.

Two of them, and nothing else touches a machine:

* `HostReader`, here, for the observation views. Read only by construction.
* the configuration plane adapter, from M1, which reaches every node over SSH
  with `ansible-runner`, including the local one.

Each has a fake implementation so the whole test suite runs on a laptop with no
cluster, no libvirt and no container.
"""
