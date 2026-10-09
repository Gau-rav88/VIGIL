from __future__ import annotations

import collections
import datetime
import math
import uuid
from typing import Any

import numpy as np
from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

from .base import Detector


class PriceJumpDetector(Detector):
    """Detects price jumps via 1-min log returns vs 1-h robust sigma (MAD * 1.4826)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        # symbol -> deque of (ts, price, trade_id, buyer, seller)
        self.price_history: dict[str, collections.deque[tuple[float, float, str, str, str]]] = (
            collections.defaultdict(lambda: collections.deque(maxlen=3600))
        )
        # symbol -> deque of 1-min returns over the last 1 hour
        self.returns_1h: dict[str, collections.deque[float]] = collections.defaultdict(
            lambda: collections.deque(maxlen=60)
        )
        self.last_fired: dict[str, float] = {}

    def on_event(self, event_type: str, data: dict[str, Any]) -> list[AnomalyEvent]:
        if event_type != "trade":
            return []

        symbol = str(data.get("symbol", "UNKNOWN"))
        ts = self.parse_ts(data.get("ts_exchange"))
        price = float(data.get("price", 0.0))
        trade_id = str(data.get("trade_id", ""))
        buyer = data.get("buyer", {}).get("account_id", "")
        seller = data.get("seller", {}).get("account_id", "")

        if price <= 0.0:
            return []

        history = self.price_history[symbol]
        history.append((ts, price, trade_id, buyer, seller))

        # We look for a price ~60 seconds ago
        target_ts = ts - 60.0
        past_price: float | None = None
        past_tid: str = ""

        # Binary search or scan backwards for price ~60s ago
        for past in history:
            if past[0] <= target_ts:
                past_price = past[1]
                past_tid = past[2]
            else:
                break

        if past_price is None or past_price <= 0.0:
            return []

        # 1-min log return
        r = math.log(price / past_price)
        self.returns_1h[symbol].append(r)

        # Robust sigma from 1-h returns (need at least 10 returns)
        rets = list(self.returns_1h[symbol])
        if len(rets) < 5:
            # Baseline proxy if early
            sigma = 0.01
        else:
            arr = np.array(rets, dtype=float)
            med = float(np.median(arr))
            mad = float(np.median(np.abs(arr - med)))
            sigma = max(mad * 1.4826, 0.005)

        tier = self.get_tier(symbol)
        tier_cfg = self.config.get("tiers", {}).get(tier, {}).get("price_jump", {})
        sigma_thr = float(tier_cfg.get("sigma_thr", 5.0))

        abs_r = abs(r)
        if abs_r >= sigma_thr * sigma:
            last_t = self.last_fired.get(symbol, 0.0)
            if ts - last_t >= 30.0:
                self.last_fired[symbol] = ts
                score = min(1.0, max(0.1, abs_r / (10.0 * sigma)))
                severity = self.map_severity(score)

                ev_refs = [EvidenceRef(kind="trade_id", ref=trade_id)]
                if past_tid:
                    ev_refs.append(EvidenceRef(kind="trade_id", ref=past_tid))

                participants = [p for p in [buyer, seller] if p]
                now_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
                start_iso = datetime.datetime.fromtimestamp(
                    max(0.0, ts - 60.0), tz=datetime.timezone.utc
                ).isoformat()

                return [
                    AnomalyEvent(
                        schema_version="1.0.0",
                        anomaly_id=str(uuid.uuid4()),
                        type="PRICE_JUMP",
                        source_agent="quant_telemetry",
                        symbol=symbol,
                        window_start=start_iso,
                        window_end=now_iso,
                        score=round(score, 4),
                        severity=severity,
                        metrics={
                            "log_return": round(r, 4),
                            "abs_return_pct": round(abs((price - past_price) / past_price) * 100.0, 2),
                            "sigma": round(sigma, 5),
                            "sigma_multiple": round(abs_r / sigma, 2),
                            "current_price": price,
                            "baseline_price": past_price,
                        },
                        participants=participants,
                        evidence_refs=ev_refs,
                        detector_version=self.detector_version,
                        config_hash=self.config_hash,
                        detected_at=now_iso,
                    )
                ]

        return []
