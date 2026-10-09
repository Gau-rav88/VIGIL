import hashlib
import json

import numpy as np
from simulator.market_model import MarketModel
from simulator.social_model import SocialModel


def generate_event_stream_hash(scenario_id: str, seed: int, steps: int = 15) -> str:
    cfg = {
        "id": scenario_id,
        "duration_s": 60,
        "symbols": 5,
        "social": {"channels": 3},
    }
    rng = np.random.default_rng(np.random.PCG64(seed))
    market_model = MarketModel(rng=rng, scenario_cfg=cfg)
    social_model = SocialModel(rng=rng, scenario_cfg=cfg, symbols=list(market_model.symbols_state.keys()))

    events = []
    t_iso = "2026-03-14T04:30:00.000000Z"
    dt_s = 0.25

    for step in range(steps):
        t_s = step * dt_s
        l3_orders, trades, l2_snaps = market_model.generate_step(t_s, dt_s, t_iso)
        for order in l3_orders:
            events.append(order.model_dump(mode="json"))
        for trade in trades:
            events.append(trade.model_dump(mode="json"))
        for snap in l2_snaps:
            events.append(snap.model_dump(mode="json"))

        messages = social_model.generate_step(t_s, dt_s, t_iso)
        for msg in messages:
            events.append(msg.model_dump(mode="json"))

    ndjson_lines = [json.dumps(ev, sort_keys=True) for ev in events]
    ndjson_bytes = "\n".join(ndjson_lines).encode("utf-8")
    return hashlib.sha256(ndjson_bytes).hexdigest()


def test_simulator_determinism_same_seed() -> None:
    # Determinism criterion: Identical scenario + seed => Byte-identical event stream
    hash1 = generate_event_stream_hash("pump_dump_ring_01", seed=42, steps=10)
    hash2 = generate_event_stream_hash("pump_dump_ring_01", seed=42, steps=10)
    assert hash1 == hash2, "Identical seed must produce identical event stream hash"


def test_simulator_determinism_different_seed() -> None:
    # Different seeds must produce divergent event streams
    hash_seed42 = generate_event_stream_hash("pump_dump_ring_01", seed=42, steps=10)
    hash_seed43 = generate_event_stream_hash("pump_dump_ring_01", seed=43, steps=10)
    assert hash_seed42 != hash_seed43, "Different seeds must produce different event streams"


def test_simulator_ground_truth_export() -> None:
    cfg = {"id": "pump_dump_ring_01", "duration_s": 60}
    rng1 = np.random.default_rng(np.random.PCG64(999))
    m1 = MarketModel(rng=rng1, scenario_cfg=cfg)
    gt1 = m1.ground_truth.to_dict() if m1.ground_truth else {}

    rng2 = np.random.default_rng(np.random.PCG64(999))
    m2 = MarketModel(rng=rng2, scenario_cfg=cfg)
    gt2 = m2.ground_truth.to_dict() if m2.ground_truth else {}

    assert gt1 == gt2
