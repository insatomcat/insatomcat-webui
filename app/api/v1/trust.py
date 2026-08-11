# Copyright (C) 2026, RTE (http://www.rte-france.com)
# SPDX-License-Identifier: Apache-2.0

"""Trust relations.

At M1 there is exactly one, the relation this node has with itself, and it is
read only from here: it is provisioned at startup because without it nothing
converges at all. Invitations and peer relations arrive at M3.

It is worth showing even though there is only one of it. An operator debugging
a failed run needs to see that the relation exists, that `sshd` would accept
it, and which key it uses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import Role, User
from app.core.errors import ApiError
from app.core.security import require_role
from app.trust.service import TrustRelation, TrustService

router = APIRouter(prefix="/trust", tags=["trust"])

viewer = Depends(require_role(Role.VIEWER))
admin = Depends(require_role(Role.ADMIN))


def _service(request: Request) -> TrustService:
    return request.app.state.trust_service


@router.get("/relations")
def relations(request: Request, user: User = viewer) -> list[TrustRelation]:
    return _service(request).relations(request.app.state.node_hostname)


@router.delete("/relations/{comment}", status_code=204, response_class=Response)
def revoke(request: Request, comment: str, user: User = admin) -> Response:
    """Remove one relation, identified by the comment on its key line.

    Revoking the self relation is allowed and is occasionally the right thing,
    for instance before decommissioning a machine. It also means this node can
    no longer converge itself until it is provisioned again, which the run
    preconditions will say in as many words.
    """
    if not _service(request).revoke(comment):
        raise ApiError("unknown_relation", f"There is no relation {comment}.", 404)
    return Response(status_code=204)
