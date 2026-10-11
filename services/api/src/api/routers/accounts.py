from __future__ import annotations

from typing import Any

from api.auth import User, require_roles
from api.deps import get_pool
from api.errors import ProblemException
from evidence_engine.reveal import IdentityRevealService
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


class RevealRequest(BaseModel):
    case_id: str
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

    pool = get_pool()
    if not pool:
        try:
            from tests.fixtures.demo.fixtures import is_demo_enabled
            if is_demo_enabled():
                return {
                    "identity_type": "SYNTHETIC",
                    "label": "DEMO-SYNTHETIC",
                    "note": "demo fixture",
                    "data_source": "demo_fixture",
                }
        except ImportError:
            pass
        raise ProblemException(
            status_code=503,
            title="Service Unavailable",
            detail="Database connection pool unavailable",
            type_uri="https://api.vigil.dev/errors/dependency-failed",
        )

    service = IdentityRevealService(pool)
    try:
        identity = await service.reveal_account(
            case_id=req.case_id,
            account_id=account_id,
            officer_id=user.sub,
            role=user.role,
            justification=req.justification,
        )
        return identity
    except ValueError as exc:
        raise ProblemException(
            status_code=400,
            title="Bad Request",
            detail=str(exc),
            type_uri="https://api.vigil.dev/errors/bad-request",
        )
    except (KeyError, LookupError) as exc:
        detail = str(exc).strip("'\"")
        raise ProblemException(
            status_code=404,
            title="Not Found",
            detail=detail,
            type_uri="https://api.vigil.dev/errors/not-found",
        )
    except Exception as exc:
        raise ProblemException(
            status_code=500,
            title="Internal Server Error",
            detail=f"Identity reveal failed: {exc}",
            type_uri="https://api.vigil.dev/errors/server-error",
        )
