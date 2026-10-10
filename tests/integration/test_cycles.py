from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from attribution.cycles import CycleDetector
from simulator.market_model import MarketModel

ROOT_DIR = Path(__file__).resolve().parents[2]


def load_scenario(name: str) -> dict[str, Any]:
    path = ROOT_DIR / "config" / "scenarios" / f"{name}.yaml"
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("id", name)
    return cfg


def generate_scenario_trades(scenario_name: str, seed: int = 42, duration_s: float = 600.0) -> list[dict[str, Any]]:
    cfg = load_scenario(scenario_name)
    rng = np.random.default_rng(np.random.PCG64(seed))
    model = MarketModel(rng=rng, scenario_cfg=cfg)

    trades: list[dict[str, Any]] = []
    base_dt = datetime.datetime(2026, 3, 14, 4, 30, 0, tzinfo=datetime.timezone.utc)
    dt_s = 0.25
    steps = int(duration_s / dt_s)

    for step in range(steps):
        t_s = step * dt_s
        t_iso = (base_dt + datetime.timedelta(seconds=t_s)).isoformat()
        _, step_trades, _ = model.generate_step(t_s, dt_s, t_iso)
        for tr in step_trades:
            if tr.symbol == "ZENITHSME":
                trades.append({
                    "seller": tr.seller.account_id,
                    "buyer": tr.buyer.account_id,
                    "qty": tr.qty,
                    "price": tr.price,
                    "ts_ms": int((base_dt + datetime.timedelta(seconds=t_s)).timestamp() * 1000),
                    "trade_id": tr.trade_id,
                })

    return trades


def test_cycles_pump_dump_ring_detected() -> None:
    # AC-GRA-02: returns all injected cycles (length 2-5)
    trades = generate_scenario_trades("pump_dump_ring_01", seed=42, duration_s=1200.0)
    detector = CycleDetector(min_len=2, max_len=6, qty_tol=0.05)
    cycles = detector.find_cycles(trades)

    assert len(cycles) > 0, "Expected wash cycles in pump_dump_ring_01"
    lengths = {c.length for c in cycles}
    # Injected wash cycles have lengths 2, 3, 4
    assert any(length in (2, 3, 4) for length in lengths)
    for c in cycles:
        assert 2 <= c.length <= 6
        assert c.cycle_volume > 0


def test_cycles_baseline_clean() -> None:
    # AC-GRA-02: zero cycles detected on baseline_01
    trades = generate_scenario_trades("baseline_01", seed=42, duration_s=600.0)
    detector = CycleDetector(min_len=2, max_len=6, qty_tol=0.05)
    cycles = detector.find_cycles(trades)

    assert len(cycles) == 0, f"Expected 0 cycles on baseline_01, got {len(cycles)}"
