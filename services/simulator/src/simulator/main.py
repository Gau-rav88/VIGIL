import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="VIGIL Simulator", version="1.0.0")

_active_scenario: str | None = None


@app.get("/status")
async def get_status() -> dict[str, str | None]:
    return {"active_scenario": _active_scenario}


@app.post("/scenarios/{scenario_id}/start")
async def start_scenario(scenario_id: str, speed: float = 1.0, seed: int = 42) -> dict[str, str | float | int]:
    global _active_scenario
    _active_scenario = scenario_id
    return {"status": "started", "scenario_id": scenario_id, "speed": speed, "seed": seed}


@app.post("/scenarios/{scenario_id}/stop")
async def stop_scenario(scenario_id: str) -> dict[str, str]:
    global _active_scenario
    _active_scenario = None
    return {"status": "stopped", "scenario_id": scenario_id}


@app.websocket("/ws/market")
async def ws_market(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/social")
async def ws_social(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


def main() -> None:
    uvicorn.run("simulator.main:app", host="0.0.0.0", port=8090, loop="uvloop")


if __name__ == "__main__":
    main()
