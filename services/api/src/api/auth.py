from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine

import jwt
from fastapi import Request
from vigil_common.config import get_settings

from api.errors import ProblemException


@dataclass
class User:
    sub: str
    role: str


async def get_current_user(request: Request) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ProblemException(
            status_code=401,
            title="Unauthorized",
            detail="Missing or malformed Authorization header. Expected Bearer token.",
            type_uri="https://api.vigil.dev/errors/unauthorized",
        )

    token = auth_header[7:].strip()
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.JWT_HS256_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        sub = str(payload.get("sub", "anon"))
        role = str(payload.get("role", "auditor_readonly"))
        return User(sub=sub, role=role)
    except jwt.PyJWTError as exc:
        raise ProblemException(
            status_code=401,
            title="Unauthorized",
            detail=f"Invalid or expired JWT token: {exc}",
            type_uri="https://api.vigil.dev/errors/unauthorized",
        )


async def optional_user(request: Request) -> User | None:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        return await get_current_user(request)
    except Exception:
        return None


def require_roles(*allowed_roles: str) -> Callable[[Request], Coroutine[Any, Any, User]]:
    async def dependency(request: Request) -> User:
        user = await get_current_user(request)
        if user.role not in allowed_roles:
            raise ProblemException(
                status_code=403,
                title="Forbidden",
                detail=f"Role '{user.role}' does not have permission for this resource. Allowed roles: {list(allowed_roles)}",
                type_uri="https://api.vigil.dev/errors/forbidden",
            )
        return user

    return dependency
