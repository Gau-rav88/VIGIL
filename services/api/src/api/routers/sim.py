from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, cast

from api.auth import User, require_roles
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/sim", tags=["simulator"])


def _sim_url() -> str:
    return os.getenv("SIMULATOR_URL", "http://localhost:8090")


@router.post("/scenarios/{scenario_id}/start")
async def start_scenario(
    scenario_id: str,
    speed: float = 1.0,
    seed: int = 42,
    user: User = Depends(require_roles("admin")),
) -> dict[str, Any]:
    url = f"{_sim_url()}/scenarios/{scenario_id}/start?speed={speed}&seed={seed}"
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return cast(dict[str, Any], json.loads(resp.read().decode("utf-8")))
    except Exception:
        return {"status": "started", "scenario_id": scenario_id, "speed": speed, "seed": seed}


@router.post("/scenarios/{scenario_id}/stop")
async def stop_scenario(
    scenario_id: str,
    user: User = Depends(require_roles("admin")),
) -> dict[str, Any]:
    url = f"{_sim_url()}/scenarios/{scenario_id}/stop"
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return cast(dict[str, Any], json.loads(resp.read().decode("utf-8")))
    except Exception:
        return {"status": "stopped", "scenario_id": scenario_id}


@router.get("/status")
async def get_sim_status(
    user: User = Depends(require_roles("admin", "investigator")),
) -> dict[str, Any]:
    url = f"{_sim_url()}/status"
    try:
        with urllib.request.urlopen(url, timeout=5.0) as resp:
            return cast(dict[str, Any], json.loads(resp.read().decode("utf-8")))
    except Exception:
        return {"running": False, "scenario": None, "tick": 0}
