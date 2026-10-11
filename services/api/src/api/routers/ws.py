from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any

import jwt
from api.deps import get_pool
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from vigil_common.config import get_settings

logger = logging.getLogger("api.ws")
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/v1/stream")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    topics: str = "heatmap,anomalies,cases",
    since: str | None = None,
    token: str | None = None,
) -> None:
    await websocket.accept()
    settings = get_settings()

    user_sub = "anonymous"
    user_role = "none"

    # Authenticate via query param or first message
    auth_token = token
    if not auth_token:
        try:
            # Wait up to 5s for auth message
            auth_raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            auth_msg = json.loads(auth_raw)
            if auth_msg.get("type") == "auth":
                auth_token = auth_msg.get("token")
        except Exception:
            auth_token = None

    if not auth_token:
        await websocket.send_text(
            json.dumps({"topic": "error", "data": {"error": "Unauthorized: Missing authentication token"}})
        )
        await websocket.close(code=1008)
        return

    try:
        payload = jwt.decode(
            auth_token,
            settings.JWT_HS256_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": True, "require": ["sub", "role"]},
        )
        user_sub = str(payload.get("sub"))
        user_role = str(payload.get("role"))
    except Exception as exc:
        logger.warning(f"WebSocket authentication failed: {exc}")
        await websocket.send_text(
            json.dumps({"topic": "error", "data": {"error": f"Unauthorized: {exc}"}})
        )
        await websocket.close(code=1008)
        return

    topic_set = set(t.strip() for t in topics.split(",") if t.strip())

    # Subscription ack
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ack_frame: dict[str, Any] = {
        "topic": "system",
        "ts": now_iso,
        "data": {"status": "SUBSCRIBED", "topics": list(topic_set), "sub": user_sub, "role": user_role},
    }
    await websocket.send_text(json.dumps(ack_frame))

    cursor_dt = (
        datetime.datetime.fromisoformat(since.replace("Z", "+00:00"))
        if since
        else datetime.datetime.now(datetime.timezone.utc)
    )

    tick = 0
    try:
        while True:
            tick += 1
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            now_iso = now_dt.isoformat()

            # Heartbeat every 15 seconds
            if tick % 8 == 0:
                hb: dict[str, Any] = {"topic": "heartbeat", "ts": now_iso, "data": {"status": "ALIVE"}}
                await websocket.send_text(json.dumps(hb))

            pool = get_pool()
            if pool:
                try:
                    async with pool.acquire() as conn:
                        # 1. Real anomalies stream since cursor
                        if "anomalies" in topic_set:
                            anom_rows = await conn.fetch(
                                """
                                SELECT anomaly_id, detected_at, symbol, type, severity, score, metrics
                                FROM vigil.anomalies
                                WHERE detected_at > $1
                                ORDER BY detected_at ASC LIMIT 20;
                                """,
                                cursor_dt,
                            )
                            for ar in anom_rows:
                                cursor_dt = max(cursor_dt, ar["detected_at"])
                                a_frame = {
                                    "topic": "anomalies",
                                    "ts": ar["detected_at"].isoformat(),
                                    "data": {
                                        "anomaly_id": str(ar["anomaly_id"]),
                                        "symbol": ar["symbol"],
                                        "type": ar["type"],
                                        "severity": str(ar["severity"]),
                                        "score": float(ar["score"]),
                                        "metrics": dict(ar["metrics"]) if ar["metrics"] else {},
                                    },
                                }
                                await websocket.send_text(json.dumps(a_frame))

                        # 2. Real cases stream since cursor
                        if "cases" in topic_set:
                            case_rows = await conn.fetch(
                                """
                                SELECT case_id, symbol, exchange, status, updated_at, overall_confidence
                                FROM vigil.cases
                                WHERE updated_at > $1
                                ORDER BY updated_at ASC LIMIT 10;
                                """,
                                cursor_dt,
                            )
                            for cr in case_rows:
                                cursor_dt = max(cursor_dt, cr["updated_at"])
                                c_frame = {
                                    "topic": "cases",
                                    "ts": cr["updated_at"].isoformat(),
                                    "data": {
                                        "case_id": str(cr["case_id"]),
                                        "symbol": cr["symbol"],
                                        "exchange": cr["exchange"],
                                        "status": str(cr["status"]),
                                        "overall_confidence": float(cr["overall_confidence"] or 0.0),
                                    },
                                }
                                await websocket.send_text(json.dumps(c_frame))

                        # 3. Heatmap updates every 4 seconds if subscribed
                        if "heatmap" in topic_set and tick % 2 == 0:
                            mrs_rows = await conn.fetch(
                                """
                                SELECT symbol, mrs, ts
                                FROM vigil.mrs_1m
                                ORDER BY ts DESC LIMIT 10;
                                """
                            )
                            if mrs_rows:
                                h_data = [
                                    {"symbol": r["symbol"], "mrs": float(r["mrs"]), "bucket": r["ts"].isoformat()}
                                    for r in mrs_rows
                                ]
                                h_frame = {
                                    "topic": "heatmap",
                                    "ts": now_iso,
                                    "data": h_data,
                                }
                                await websocket.send_text(json.dumps(h_frame))

                except Exception as exc:
                    logger.debug(f"Error during WS DB poll: {exc}")

            await asyncio.sleep(2.0)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug(f"WebSocket stream terminated: {exc}")
