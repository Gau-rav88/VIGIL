from __future__ import annotations

import logging
from typing import Any

from api.auth import User, require_roles
from api.deps import get_pool
from api.errors import ProblemException
from api.pagination import decode_cursor, encode_cursor
from fastapi import APIRouter, Depends, Query

logger = logging.getLogger("api.anomalies")
router = APIRouter(prefix="/api/v1", tags=["anomalies"])


@router.get("/anomalies")
async def list_anomalies(
    symbol: str | None = None,
    anomaly_type: str | None = Query(default=None, alias="type"),
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    min_score: float | None = None,
    limit: int = 50,
    cursor: str | None = None,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    pool = get_pool()
    if pool is None:
        raise ProblemException(
            status_code=503,
            title="Service Unavailable",
            detail="Database connection pool is not available",
            type_uri="https://api.vigil.dev/errors/dependency-failure",
        )

    items: list[dict[str, Any]] = []
    try:
        query = (
            "SELECT anomaly_id, detected_at AS ts, symbol, type, severity, score, metrics AS payload "
            "FROM vigil.anomalies WHERE 1=1"
        )
        params: list[Any] = []

        if symbol and isinstance(symbol, str):
            params.append(symbol)
            query += f" AND symbol = ${len(params)}"
        if anomaly_type and isinstance(anomaly_type, str):
            params.append(anomaly_type)
            query += f" AND type = ${len(params)}"
        if min_score is not None:
            params.append(min_score)
            query += f" AND score >= ${len(params)}"
        if from_ts and isinstance(from_ts, str):
            params.append(from_ts)
            query += f" AND detected_at >= ${len(params)}::timestamptz"
        if to_ts and isinstance(to_ts, str):
            params.append(to_ts)
            query += f" AND detected_at <= ${len(params)}::timestamptz"

        decoded_cursor = decode_cursor(cursor)
        if decoded_cursor:
            params.append(decoded_cursor)
            query += f" AND detected_at < ${len(params)}::timestamptz"

        params.append(limit)
        query += f" ORDER BY detected_at DESC LIMIT ${len(params)}"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            for r in rows:
                items.append({
                    "anomaly_id": str(r["anomaly_id"]),
                    "ts": r["ts"].isoformat(),
                    "symbol": r["symbol"],
                    "type": r["type"],
                    "severity": str(r["severity"]),
                    "score": float(r["score"]),
                    "payload": r["payload"] if r["payload"] is not None else {},
                })
    except Exception as exc:
        logger.error("Failed querying anomalies from database", exc_info=True)
        raise ProblemException(
            status_code=503,
            title="Database Error",
            detail="Failed to query anomalies from TimescaleDB",
            type_uri="https://api.vigil.dev/errors/database-error",
        ) from exc

    next_cursor = encode_cursor(items[-1]["ts"]) if items else None
    state = "READY" if items else "EMPTY"
    return {"items": items, "next_cursor": next_cursor, "total": len(items), "state": state}


@router.get("/live/alerts")
async def get_live_alerts_alias(
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    res = await list_anomalies(anomaly_type=None, from_ts=None, to_ts=None, limit=20, user=user)
    alerts: list[dict[str, Any]] = []
    for item in res.get("items", []):
        alerts.append({
            "id": item["anomaly_id"],
            "ts": item["ts"],
            "symbol": item["symbol"],
            "type": item["type"],
            "severity": item["severity"],
            "confidence": item["score"],
            "summary": f"{item['type']} detected on {item['symbol']} (score: {item['score']})",
            "details": item.get("payload") or {},
        })
    return {"items": alerts, "total": len(alerts), "state": res.get("state", "EMPTY")}
