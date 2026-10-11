from __future__ import annotations

import asyncio
import datetime
import os
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from simulator.groundtruth import registry
from simulator.market_model import MarketModel
from simulator.social_model import SocialModel

DEFAULT_BASE_DT = datetime.datetime(2026, 3, 14, 4, 30, 0, tzinfo=datetime.timezone.utc)


def resolve_epoch(epoch_str: str | None = None) -> datetime.datetime:
    raw = epoch_str or os.getenv("SIM_EPOCH")
    if not raw:
        return DEFAULT_BASE_DT
    raw = raw.strip()
    if raw.lower() == "now":
        return datetime.datetime.now(datetime.timezone.utc)
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(raw)
    except Exception:
        return DEFAULT_BASE_DT


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
        self.epoch: datetime.datetime = DEFAULT_BASE_DT
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
        self.dropped_frames = {
            "market": 0,
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

    async def start(
        self,
        scenario_id: str,
        speed: float = 1.0,
        seed: int = 42,
        epoch: str | None = None,
        wait_subscribers_s: float | None = None,
    ) -> dict[str, Any]:
        if self.running:
            await self.stop()

        wait_timeout = float(
            wait_subscribers_s
            if wait_subscribers_s is not None
            else os.getenv("SIM_WAIT_SUBSCRIBERS_S", "30.0")
        )
        if wait_timeout > 0:
            loop = asyncio.get_running_loop()
            start_wait = loop.time()
            while (loop.time() - start_wait) < wait_timeout:
                if len(self.market_subscribers) >= 1 and len(self.social_subscribers) >= 1:
                    break
                await asyncio.sleep(0.1)

            if len(self.market_subscribers) < 1 or len(self.social_subscribers) < 1:
                missing: list[str] = []
                if len(self.market_subscribers) < 1:
                    missing.append("market")
                if len(self.social_subscribers) < 1:
                    missing.append("social")
                self.running = False
                raise RuntimeError(
                    f"Simulator start failed: timed out after {wait_timeout}s waiting for subscriber(s): {', '.join(missing)}"
                )

        self.epoch = resolve_epoch(epoch)
        self.active_scenario_id = scenario_id
        self.speed = max(0.1, speed)
        self.seed = seed
        self.sim_time_s = 0.0
        self.running = True
        self.events_emitted = {"trades": 0, "l2": 0, "l3": 0, "social": 0}
        self.dropped_frames = {"market": 0, "social": 0}

        scenario_cfg = self.load_scenario_config(scenario_id)
        scenario_cfg.setdefault("run_id", f"{scenario_id[:6]}_{seed}_{int(self.epoch.timestamp()) % 100000}")

        # Deterministic PCG64 PRNG
        rng = np.random.default_rng(np.random.PCG64(seed))

        market_model = MarketModel(rng=rng, scenario_cfg=scenario_cfg, base_dt=self.epoch)
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
            "epoch": self.epoch.isoformat(),
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
            "epoch": self.epoch.isoformat(),
            "events_emitted": self.events_emitted,
            "dropped_frames": self.dropped_frames,
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
        base_dt = self.epoch

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
                self.dropped_frames["market"] += 1

    def _broadcast_social(self, frame: dict[str, Any]) -> None:
        for q in list(self.social_subscribers):
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                self.dropped_frames["social"] += 1


manager = ScenarioManager()
