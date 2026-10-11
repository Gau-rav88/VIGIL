from __future__ import annotations

import logging
from typing import Any

from api.auth import User, require_roles
from api.deps import get_pool
from api.errors import ProblemException
from api.pagination import decode_cursor, encode_cursor
from fastapi import APIRouter, Depends, Query

logger = logging.getLogger("api.social")
router = APIRouter(prefix="/api/v1/social", tags=["social"])


@router.get("/signals")
async def list_social_signals(
    ticker: str | None = None,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    channel: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    can_view_unredacted = user.role in ("investigator", "compliance_officer")
    pool = get_pool()
    if pool is None:
        try:
            from tests.fixtures.demo.fixtures import DEMO_SIGNALS, is_demo_enabled
            if is_demo_enabled():
                demo_items = []
                for s in DEMO_SIGNALS:
                    raw_text = s.get("raw_text", "")
                    text_out = raw_text if can_view_unredacted else "[REDACTED — INVESTIGATOR PRIVILEGE REQUIRED]"
                    demo_items.append({
                        "signal_id": s["signal_id"],
                        "ts": s["ts"],
                        "ticker": s["ticker"],
                        "platform": s["platform"],
                        "channel_id": s["channel_id"],
                        "author_id": s["author_id"],
                        "cta_class": s["cta_class"],
                        "confidence": s["confidence"],
                        "text": text_out,
                        "data_source": "demo_fixture",
                    })
                return {"items": demo_items, "next_cursor": None, "total": len(demo_items), "state": "READY"}
        except ImportError:
            pass

        raise ProblemException(
            status_code=503,
            title="Service Unavailable",
            detail="Database connection pool is not available",
            type_uri="https://api.vigil.dev/errors/dependency-failure",
        )

    can_view_unredacted = user.role in ("investigator", "compliance_officer")
    items: list[dict[str, Any]] = []

    try:
        query = (
            "SELECT s.signal_id, s.ts, s.ticker, s.platform, s.channel_id, s.author_id, "
            "s.cta_class, s.cta_confidence AS confidence, m.text AS raw_text "
            "FROM vigil.social_signals s "
            "LEFT JOIN vigil.social_messages m ON s.message_event_id = m.event_id "
            "WHERE 1=1"
        )
        params: list[Any] = []

        if ticker:
            params.append(ticker)
            query += f" AND s.ticker = ${len(params)}"
        if channel:
            params.append(channel)
            query += f" AND s.channel_id = ${len(params)}"
        if from_ts:
            params.append(from_ts)
            query += f" AND s.ts >= ${len(params)}::timestamptz"
        if to_ts:
            params.append(to_ts)
            query += f" AND s.ts <= ${len(params)}::timestamptz"

        decoded_cursor = decode_cursor(cursor)
        if decoded_cursor:
            params.append(decoded_cursor)
            query += f" AND s.ts < ${len(params)}::timestamptz"

        params.append(limit)
        query += f" ORDER BY s.ts DESC LIMIT ${len(params)}"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            for r in rows:
                raw_text = r["raw_text"] or ""
                text_out = raw_text if can_view_unredacted else "[REDACTED — INVESTIGATOR PRIVILEGE REQUIRED]"
                items.append({
                    "signal_id": str(r["signal_id"]),
                    "ts": r["ts"].isoformat(),
                    "ticker": r["ticker"],
                    "platform": r["platform"],
                    "channel_id": r["channel_id"],
                    "author_id": r["author_id"],
                    "cta_class": r["cta_class"],
                    "confidence": float(r["confidence"]) if r["confidence"] is not None else 0.0,
                    "text": text_out,
                })
    except Exception as exc:
        logger.error("Failed querying social signals from database", exc_info=True)
        raise ProblemException(
            status_code=503,
            title="Database Error",
            detail="Failed to query social signals from TimescaleDB",
            type_uri="https://api.vigil.dev/errors/database-error",
        ) from exc

    next_cursor = encode_cursor(items[-1]["ts"]) if items else None
    state = "READY" if items else "EMPTY"
    return {"items": items, "next_cursor": next_cursor, "total": len(items), "state": state}
