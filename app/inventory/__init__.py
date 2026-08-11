# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""The inventory: the desired state, and the product.

Everything this service does to a machine, it does by changing this file and
asking Ansible to converge. The claim the whole design rests on is that the
file produced here is indistinguishable from a hand written one: export it,
run the same playbooks from a conventional control machine, and observe no
change. The golden file tests are what keep that claim honest.
"""
