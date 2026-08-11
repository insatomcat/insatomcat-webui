# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Version 1 of the REST API, specified in docs/api.md."""

from fastapi import APIRouter

from app.api.v1 import auth, node

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(node.router)
