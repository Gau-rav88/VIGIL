from __future__ import annotations

import datetime
import json
from typing import Any

import asyncpg
from vigil_common.logging import get_logger

from api.auth import User
from api.errors import ProblemException

logger = get_logger("audit")


async def record_audit_log(
    pool: asyncpg.Pool | None,
    user: User | None,
    method: str,
    path: str,
    status: int,
    request_hash: str | None = None,
    meta: dict[str, Any] | None = None,
    fail_closed: bool = False,
) -> None:
    is_sensitive = fail_closed or any(kw in path for kw in ("/reveal", "/review", "/publish"))

    if not pool:
        logger.error("Audit log failed: database pool not available", path=path, method=method, status=status)
        if is_sensitive:
            raise ProblemException(
                503,
                "Service Unavailable",
                "Audit log recording unavailable for sensitive action",
                type_uri="https://api.vigil.dev/errors/dependency-failed",
            )
        return

    try:
        user_id = user.sub if user else "anonymous"
        role = user.role if user else "public"
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        meta_json = json.dumps(meta or {})
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO vigil.audit_log (ts, user_id, role, method, path, status, request_hash, meta)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb);
                """,
                now_dt,
                user_id,
                role,
                method,
                path,
                status,
                (request_hash or ("0" * 64))[:64],
                meta_json,
            )
    except Exception as exc:
        logger.error(
            "Failed to record audit log",
            error=str(exc),
            path=path,
            method=method,
            status=status,
            is_sensitive=is_sensitive,
        )
        if is_sensitive:
            raise ProblemException(
                503,
                "Service Unavailable",
                f"Audit logging failed for sensitive forensic action: {exc}",
                type_uri="https://api.vigil.dev/errors/dependency-failed",
            )
