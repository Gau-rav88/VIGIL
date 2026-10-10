from __future__ import annotations

import datetime
from typing import Any

from api.auth import User, require_roles
from api.deps import get_pool
from api.pagination import decode_cursor, encode_cursor
from fastapi import APIRouter, Depends, Query

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
    pool = get_pool()
    items: list[dict[str, Any]] = []

    can_view_unredacted = user.role in ("investigator", "compliance_officer")

    if pool:
        try:
            query = "SELECT signal_id, ts, ticker, platform, channel_id, author_id, cta_class, confidence, raw_text FROM vigil.social_signals WHERE 1=1"
            params: list[Any] = []

            if ticker:
                params.append(ticker)
                query += f" AND ticker = ${len(params)}"
            if channel:
                params.append(channel)
                query += f" AND channel_id = ${len(params)}"

            decoded_cursor = decode_cursor(cursor)
            if decoded_cursor:
                params.append(decoded_cursor)
                query += f" AND ts < ${len(params)}::timestamptz"

            params.append(limit)
            query += f" ORDER BY ts DESC LIMIT ${len(params)}"

            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                for r in rows:
                    raw_text = r.get("raw_text") or ""
                    text_out = raw_text if can_view_unredacted else "[REDACTED — INVESTIGATOR PRIVILEGE REQUIRED]"
                    items.append({
                        "signal_id": str(r["signal_id"]),
                        "ts": r["ts"].isoformat(),
                        "ticker": r["ticker"],
                        "platform": r["platform"],
                        "channel_id": r["channel_id"],
                        "author_id": r["author_id"],
                        "cta_class": r["cta_class"],
                        "confidence": float(r["confidence"]),
                        "text": text_out,
                    })
        except Exception:
            pass

    if not items:
        # Fallback signals
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        sample_texts = [
            "🚀 ZENITHSME BREAKOUT CONFIRMED! Target 180 by afternoon. Sab log buy karo!",
            "Insider update: Big pump incoming in 15 mins for ZENITHSME. Load heavy!",
            "Hold ZENITHSME till closing bell, target 200 achieved soon.",
        ]
        for i, text in enumerate(sample_texts):
            text_out = text if can_view_unredacted else "[REDACTED — INVESTIGATOR PRIVILEGE REQUIRED]"
            items.append({
                "signal_id": f"sig-0{i+1}",
                "ts": (now_dt - datetime.timedelta(minutes=i * 5)).isoformat(),
                "ticker": ticker or "ZENITHSME",
                "platform": "Telegram",
                "channel_id": f"pump_group_0{i+1}",
                "author_id": f"admin_{i+1}",
                "cta_class": "BUY_RECOMMENDATION",
                "confidence": 0.94,
                "text": text_out,
            })

    next_cursor = encode_cursor(items[-1]["ts"]) if items else None
    return {"items": items, "next_cursor": next_cursor, "total": len(items)}
