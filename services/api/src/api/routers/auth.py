from __future__ import annotations

import jwt
from api.auth import User, get_current_user
from api.errors import ProblemException
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from vigil_common.config import get_settings
from vigil_common.timeutil import now_utc

router = APIRouter(prefix="/api/v1", tags=["auth"])


class DevTokenRequest(BaseModel):
    sub: str
    role: str = "compliance_officer"


@router.post("/auth/dev-token")
async def issue_dev_token(req: DevTokenRequest) -> dict[str, str]:
    settings = get_settings()
    if settings.ENV == "prod":
        raise ProblemException(
            status_code=403,
            title="Forbidden",
            detail="Dev tokens are disabled in production environment",
            type_uri="https://api.vigil.dev/errors/forbidden",
        )

    token = jwt.encode(
        {"sub": req.sub, "role": req.role, "iat": now_utc().timestamp()},
        settings.JWT_HS256_SECRET,
        algorithm="HS256",
    )
    return {"token": token}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"sub": user.sub, "role": user.role}
