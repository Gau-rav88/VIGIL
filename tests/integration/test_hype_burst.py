from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from simulator.social_model import SocialModel
from social_intel.engine import SocialIntelEngine


def test_pump_dump_ring_01_emits_hype_burst_within_60s() -> None:
    """
    AC-SOC-03: pump_dump_ring_01 scenario emits HYPE_BURST for ZENITHSME
    within 60s of the first coordinated message.
    """
    cfg_path = Path("config/scenarios/pump_dump_ring_01.yaml")
    assert cfg_path.exists(), "pump_dump_ring_01.yaml configuration not found"

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    rng = np.random.default_rng(np.random.PCG64(42))
    sm = SocialModel(rng=rng, scenario_cfg=cfg, symbols=["ZENITHSME"])
    engine = SocialIntelEngine()

    base_dt = datetime.datetime(2026, 3, 14, 4, 30, 0, tzinfo=datetime.timezone.utc)
    dt_s = 0.5
    sim_time_s = 0.0

    first_coordinated_ts: float | None = None
    burst_anomalies: list[tuple[float, Any]] = []

    while sim_time_s < 400.0:
        cur_time = base_dt + datetime.timedelta(seconds=sim_time_s)
        iso_time = cur_time.isoformat()
        msgs = sm.generate_step(sim_time_s, dt_s, iso_time)

        for m in msgs:
            m_dict = m.model_dump()
            # The burst configuration in pump_dump_ring_01 sets t0_s: 300
            if "ZENITHSME" in m.text and sim_time_s >= 300.0 and first_coordinated_ts is None:
                first_coordinated_ts = sim_time_s

            signals, anomalies, hype_records = engine.process_message(m_dict)
            for anom in anomalies:
                if anom.type == "HYPE_BURST" and anom.symbol == "ZENITHSME":
                    burst_anomalies.append((sim_time_s, anom))

        sim_time_s += dt_s

    assert first_coordinated_ts is not None, "Coordinated pump messages were never generated"
    assert len(burst_anomalies) >= 1, "No HYPE_BURST anomaly was emitted for ZENITHSME"

    first_burst_ts, burst_anom = burst_anomalies[0]
    elapsed_since_first_msg = first_burst_ts - first_coordinated_ts

    print(
        f"\nAC-SOC-03 Verification: First pump msg at t={first_coordinated_ts:.1f}s, "
        f"HYPE_BURST emitted at t={first_burst_ts:.1f}s (elapsed: {elapsed_since_first_msg:.1f}s)"
    )

    # Verification criteria from PRD AC-SOC-03: within 60s of first coordinated message
    assert elapsed_since_first_msg <= 60.0, (
        f"HYPE_BURST emitted too late: {elapsed_since_first_msg:.1f}s > 60.0s threshold"
    )
    assert burst_anom.type == "HYPE_BURST"
    assert burst_anom.symbol == "ZENITHSME"
    assert burst_anom.score >= 0.70
    assert burst_anom.metrics.get("sustained_duration_s", 0) >= 30.0
