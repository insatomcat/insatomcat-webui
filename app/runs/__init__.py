# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Running the upstream playbooks, and making the result readable.

This is the second of the two host adapters, and the only one that changes a
machine. It changes them the way SEAPATH always has: by running the playbooks
the CI runs, unmodified, from a collection installed at image build time.
"""
