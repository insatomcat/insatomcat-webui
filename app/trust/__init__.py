# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""SSH trust between this service and the `ansible` accounts it drives.

Establishing trust between machines that have never met is the one part of this
design that is irreducibly imperative, and it is bounded to exactly two files:
the service's own keys under `/etc/seapath/webui/ssh/`, and single lines
appended to an `authorized_keys` that belongs to someone else.

That second file is the dangerous one. It arrives from the ISO carrying the
site key, which is how a conventional Ansible control machine reaches the node.
Every operation here adds or removes whole lines matched by their comment, and
nothing else in the file is ever touched.
"""
