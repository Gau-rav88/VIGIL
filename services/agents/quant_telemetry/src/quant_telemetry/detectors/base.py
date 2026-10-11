from __future__ import annotations

import abc
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from vigil_common.models.anomaly import AnomalyEvent


def find_detectors_config_path() -> Path:
    candidates = [
        Path("/app/config/detectors.yaml"),
        Path(__file__).resolve().parents[5] / "config" / "detectors.yaml",
        Path.cwd() / "config" / "detectors.yaml",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return Path("config/detectors.yaml")


def load_detectors_config() -> dict[str, Any]:
    cfg_path = find_detectors_config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


class Detector(abc.ABC):
    """Abstract base class for quantitative market anomaly detectors."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_detectors_config()
        self.config_hash = self._calc_config_hash()
        self.detector_version = "1.0.0"

    def _calc_config_hash(self) -> str:
        data = json.dumps(self.config, sort_keys=True).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def get_tier(self, symbol: str) -> str:
        s = symbol.upper()
        if "SME" in s or s in ("MICROTECH", "ALPHASME", "SOLARIS", "NOVAPHARMA"):
            return "micro"
        if s in ("ACMESYSTEMS", "PRISMIND", "VORTEXSME", "STELLARSME"):
            return "mid"
        return "large"

    @staticmethod
    def map_severity(score: float) -> Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        if score < 0.4:
            return "LOW"
        if score < 0.7:
            return "MEDIUM"
        if score < 0.9:
            return "HIGH"
        return "CRITICAL"

    @staticmethod
    def parse_ts(val: Any) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                if val.endswith("Z"):
                    val = val[:-1] + "+00:00"
                return datetime.datetime.fromisoformat(val).timestamp()
            except Exception:
                pass
        return datetime.datetime.now(datetime.timezone.utc).timestamp()

    @abc.abstractmethod
    def on_event(self, event_type: str, data: dict[str, Any]) -> list[AnomalyEvent]:
        """Process incoming market event (trade, l2, or l3) and emit any detected anomalies."""
        raise NotImplementedError
