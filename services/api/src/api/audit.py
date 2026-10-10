from __future__ import annotations

import datetime
import json
from typing import Any

import asyncpg

from api.auth import User


async def record_audit_log(
    pool: asyncpg.Pool | None,
    user: User | None,
    method: str,
    path: str,
    status: int,
    request_hash: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    if not pool:
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
    except Exception:
        # Never break request flow if audit insert fails
        pass
