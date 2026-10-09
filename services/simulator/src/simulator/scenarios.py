from __future__ import annotations

import asyncio
import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from simulator.groundtruth import registry
from simulator.market_model import MarketModel
from simulator.social_model import SocialModel


def find_config_dir() -> Path:
    # Check possible locations for config/scenarios
    candidates = [
        Path("/app/config/scenarios"),
        Path(__file__).resolve().parents[4] / "config" / "scenarios",
        Path.cwd() / "config" / "scenarios",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return Path("config/scenarios")


class ScenarioManager:
    def __init__(self) -> None:
        self.scenarios_dir = find_config_dir()
        self.active_scenario_id: str | None = None
        self.speed: float = 1.0
        self.seed: int = 42
        self.sim_time_s: float = 0.0
        self.running: bool = False
        self._task: asyncio.Task[None] | None = None
        self.market_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self.social_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

        self.events_emitted = {
            "trades": 0,
            "l2": 0,
            "l3": 0,
            "social": 0,
        }

    def load_scenario_config(self, scenario_id: str) -> dict[str, Any]:
        path = self.scenarios_dir / f"{scenario_id}.yaml"
        if not path.exists():
            # Fallback baseline
            return {
                "id": scenario_id,
                "duration_s": 600,
                "symbols": 40,
                "social": {"channels": 20},
            }
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            cfg.setdefault("id", scenario_id)
            return cfg

    async def start(self, scenario_id: str, speed: float = 1.0, seed: int = 42) -> dict[str, Any]:
        if self.running:
            await self.stop()

        self.active_scenario_id = scenario_id
        self.speed = max(0.1, speed)
        self.seed = seed
        self.sim_time_s = 0.0
        self.running = True
        self.events_emitted = {"trades": 0, "l2": 0, "l3": 0, "social": 0}

        scenario_cfg = self.load_scenario_config(scenario_id)

        # Deterministic PCG64 PRNG
        rng = np.random.default_rng(np.random.PCG64(seed))

        market_model = MarketModel(rng=rng, scenario_cfg=scenario_cfg)
        social_model = SocialModel(rng=rng, scenario_cfg=scenario_cfg, symbols=list(market_model.symbols_state.keys()))

        if market_model.ground_truth:
            registry.register(market_model.ground_truth)

        self._task = asyncio.create_task(
            self._run_loop(scenario_cfg, market_model, social_model)
        )

        return {
            "status": "started",
            "scenario_id": scenario_id,
            "speed": self.speed,
            "seed": self.seed,
        }

    async def stop(self) -> dict[str, Any]:
        scenario_id = self.active_scenario_id
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self.active_scenario_id = None
        return {"status": "stopped", "scenario_id": scenario_id or ""}

    def get_status(self) -> dict[str, Any]:
        return {
            "active_scenario": self.active_scenario_id,
            "running": self.running,
            "sim_time_s": round(self.sim_time_s, 2),
            "speed": self.speed,
            "seed": self.seed,
            "events_emitted": self.events_emitted,
            "active_market_clients": len(self.market_subscribers),
            "active_social_clients": len(self.social_subscribers),
        }

    async def _run_loop(
        self,
        scenario_cfg: dict[str, Any],
        market_model: MarketModel,
        social_model: SocialModel,
    ) -> None:
        duration_s = float(scenario_cfg.get("duration_s", 1800))
        dt_s = 0.25 if self.speed <= 2.0 else min(1.0, 0.05 * self.speed)
        base_dt = datetime.datetime(2026, 3, 14, 4, 30, 0, tzinfo=datetime.timezone.utc)

        try:
            while self.running and self.sim_time_s < duration_s:
                current_time = base_dt + datetime.timedelta(seconds=self.sim_time_s)
                iso_time = current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                # 1. Market step
                l3_events, trades, l2_snaps = market_model.generate_step(
                    sim_time_s=self.sim_time_s,
                    dt_s=dt_s,
                    current_iso_time=iso_time,
                )

                # Broadcast market frames
                for t in trades:
                    frame = {"kind": "trade", "data": t.model_dump()}
                    self._broadcast_market(frame)
                    self.events_emitted["trades"] += 1

                for snap in l2_snaps:
                    frame = {"kind": "l2", "data": snap.model_dump()}
                    self._broadcast_market(frame)
                    self.events_emitted["l2"] += 1

                for ev in l3_events:
                    frame = {"kind": "l3", "data": ev.model_dump()}
                    self._broadcast_market(frame)
                    self.events_emitted["l3"] += 1

                # 2. Social step
                social_msgs = social_model.generate_step(
                    sim_time_s=self.sim_time_s,
                    dt_s=dt_s,
                    current_iso_time=iso_time,
                )

                for sm in social_msgs:
                    self._broadcast_social(sm.model_dump())
                    self.events_emitted["social"] += 1

                self.sim_time_s += dt_s
                # Real sleep scaled by speed
                sleep_s = dt_s / self.speed
                await asyncio.sleep(sleep_s)

        except asyncio.CancelledError:
            pass
        finally:
            self.running = False

    def _broadcast_market(self, frame: dict[str, Any]) -> None:
        for q in list(self.market_subscribers):
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                pass

    def _broadcast_social(self, frame: dict[str, Any]) -> None:
        for q in list(self.social_subscribers):
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                pass


manager = ScenarioManager()
