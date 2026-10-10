from __future__ import annotations

import os
from typing import Any, cast

from api.auth import User, require_roles
from api.errors import ProblemException
from evidence_engine.reveal import IdentityRevealService
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


class RevealRequest(BaseModel):
    case_id: str = "case_01"
    justification: str


@router.post("/{account_id}/reveal")
async def reveal_account_identity(
    account_id: str,
    req: RevealRequest,
    user: User = Depends(require_roles("compliance_officer")),
) -> dict[str, Any]:
    if not req.justification or len(req.justification.strip()) < 10:
        raise ProblemException(
            status_code=400,
            title="Bad Request",
            detail="Justification required (minimum 10 characters) for identity reveal",
            type_uri="https://api.vigil.dev/errors/bad-request",
        )

    dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@localhost:5434/vigil")
    service = IdentityRevealService(dsn)
    try:
        identity = await service.reveal_account(
            case_id=req.case_id,
            pseudo_id=account_id,
            officer_id=user.sub,
            justification=req.justification,
        )
        return cast(dict[str, Any], identity)
    except Exception as exc:
        raise ProblemException(
            status_code=500,
            title="Internal Server Error",
            detail=f"Identity reveal failed: {exc}",
            type_uri="https://api.vigil.dev/errors/server-error",
        )
