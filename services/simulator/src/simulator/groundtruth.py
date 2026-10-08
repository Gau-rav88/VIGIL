from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScenarioGroundTruth:
    scenario_id: str
    target_symbol: str = ""
    ring_accounts: list[str] = field(default_factory=list)
    brokers: list[str] = field(default_factory=list)
    shared_devices: dict[str, list[str]] = field(default_factory=dict)
    shared_asn: int | None = None
    wash_cycles: list[dict[str, Any]] = field(default_factory=list)
    wash_trade_ids: list[str] = field(default_factory=list)
    spoofers: list[str] = field(default_factory=list)
    social_burst_t0_s: float | None = None
    market_pump_t0_s: float | None = None
    reaction_lag_s: float | None = None
    effective_lag_s: float | None = None
    dump_start_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "target_symbol": self.target_symbol,
            "ring_accounts": self.ring_accounts,
            "brokers": self.brokers,
            "shared_devices": self.shared_devices,
            "shared_asn": self.shared_asn,
            "wash_cycles": self.wash_cycles,
            "wash_trade_ids": self.wash_trade_ids,
            "spoofers": self.spoofers,
            "social_burst_t0_s": self.social_burst_t0_s,
            "market_pump_t0_s": self.market_pump_t0_s,
            "reaction_lag_s": self.reaction_lag_s,
            "effective_lag_s": self.effective_lag_s,
            "dump_start_s": self.dump_start_s,
        }


class GroundTruthRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, ScenarioGroundTruth] = {}

    def register(self, gt: ScenarioGroundTruth) -> None:
        self._registry[gt.scenario_id] = gt

    def get(self, scenario_id: str) -> ScenarioGroundTruth | None:
        return self._registry.get(scenario_id)

    def clear(self) -> None:
        self._registry.clear()


registry = GroundTruthRegistry()
