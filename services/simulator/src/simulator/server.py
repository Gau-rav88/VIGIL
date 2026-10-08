from __future__ import annotations

import asyncio
from typing import Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from simulator.groundtruth import registry
from simulator.scenarios import manager

app = FastAPI(title="VIGIL Market & Social Simulator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
@app.get("/readyz")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
async def get_status() -> dict[str, Any]:
    return manager.get_status()


@app.post("/scenarios/{scenario_id}/start")
async def start_scenario(
    scenario_id: str,
    speed: float = 1.0,
    seed: int = 42,
) -> dict[str, Any]:
    return await manager.start(scenario_id=scenario_id, speed=speed, seed=seed)


@app.post("/scenarios/{scenario_id}/stop")
async def stop_scenario(scenario_id: str) -> dict[str, Any]:
    return await manager.stop()


@app.get("/groundtruth/{scenario_id}")
async def get_groundtruth(scenario_id: str) -> dict[str, Any]:
    gt = registry.get(scenario_id)
    if not gt:
        raise HTTPException(status_code=404, detail=f"Ground truth not found for {scenario_id}")
    return gt.to_dict()


@app.websocket("/ws/market")
async def ws_market(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2000)
    manager.market_subscribers.add(queue)
    try:
        while True:
            frame = await queue.get()
            await websocket.send_json(frame)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        manager.market_subscribers.discard(queue)


@app.websocket("/ws/social")
async def ws_social(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2000)
    manager.social_subscribers.add(queue)
    try:
        while True:
            frame = await queue.get()
            await websocket.send_json(frame)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        manager.social_subscribers.discard(queue)
