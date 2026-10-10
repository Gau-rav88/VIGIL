from __future__ import annotations

import asyncio
import datetime
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/v1/stream")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    topics: str = "heatmap,anomalies,cases",
    since: str | None = None,
) -> None:
    await websocket.accept()
    topic_set = set(t.strip() for t in topics.split(",") if t.strip())

    try:
        # Initial greeting / subscription ack
        ack_frame: dict[str, Any] = {
            "topic": "system",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "data": {"status": "SUBSCRIBED", "topics": list(topic_set)},
        }
        await websocket.send_text(json.dumps(ack_frame))

        # Periodic heartbeat and synthetic frame loop
        tick = 0
        while True:
            tick += 1
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # 1. Heartbeat every 15 seconds
            if tick % 15 == 0:
                hb: dict[str, Any] = {"topic": "heartbeat", "ts": now_iso, "data": {"status": "ALIVE"}}
                await websocket.send_text(json.dumps(hb))

            # 2. Topic updates
            if "heatmap" in topic_set and tick % 2 == 0:
                h_frame: dict[str, Any] = {
                    "topic": "heatmap",
                    "ts": now_iso,
                    "data": [
                        {"symbol": "ZENITHSME", "mrs": 0.94, "hype": 88.5, "price": 142.50},
                        {"symbol": "MICROTECH", "mrs": 0.42, "hype": 45.0, "price": 85.20},
                    ],
                }
                await websocket.send_text(json.dumps(h_frame))

            if "anomalies" in topic_set and tick % 10 == 0:
                a_frame: dict[str, Any] = {
                    "topic": "anomalies",
                    "ts": now_iso,
                    "data": {
                        "id": f"anom-{tick}",
                        "symbol": "ZENITHSME",
                        "type": "CROSS_MODAL_ALIGNMENT",
                        "score": 0.96,
                    },
                }
                await websocket.send_text(json.dumps(a_frame))

            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
