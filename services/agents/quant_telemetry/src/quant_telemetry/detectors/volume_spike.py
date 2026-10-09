from __future__ import annotations

import collections
import datetime
import uuid
from typing import Any

import numpy as np
from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

from .base import Detector


class VolumeSpikeDetector(Detector):
    """Detects volume spikes via rolling 5-s volume bins and median/MAD robust z-score."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        # symbol -> current bin timestamp (floored to 5s), current bin volume
        self.current_bins: dict[str, list[float]] = {}  # [bin_start_ts, bin_volume]
        # symbol -> deque of past 5s bin volumes (up to 360 bins = 30 minutes)
        self.history: dict[str, collections.deque[float]] = collections.defaultdict(
            lambda: collections.deque(maxlen=360)
        )
        # symbol -> consecutive bins exceeding threshold
        self.consecutive_spikes: dict[str, int] = collections.defaultdict(int)
        # symbol -> recent trade_ids in current window
        self.recent_trades: dict[str, collections.deque[str]] = collections.defaultdict(
            lambda: collections.deque(maxlen=200)
        )
        self.recent_participants: dict[str, collections.deque[str]] = collections.defaultdict(
            lambda: collections.deque(maxlen=100)
        )
        self.last_fired: dict[str, float] = {}

    def on_event(self, event_type: str, data: dict[str, Any]) -> list[AnomalyEvent]:
        if event_type != "trade":
            return []

        symbol = str(data.get("symbol", "UNKNOWN"))
        ts = self.parse_ts(data.get("ts_exchange"))
        qty = float(data.get("qty", 0))
        trade_id = str(data.get("trade_id", ""))
        buyer = data.get("buyer", {}).get("account_id", "")
        seller = data.get("seller", {}).get("account_id", "")

        if trade_id:
            self.recent_trades[symbol].append(trade_id)
        if buyer:
            self.recent_participants[symbol].append(buyer)
        if seller:
            self.recent_participants[symbol].append(seller)

        # 5-second bin boundary
        bin_start = float(int(ts // 5) * 5)
        curr = self.current_bins.get(symbol)

        anomalies: list[AnomalyEvent] = []

        if curr is None:
            self.current_bins[symbol] = [bin_start, qty]
            return []

        if bin_start > curr[0]:
            # Current bin ended! Push to history and evaluate
            finished_vol = curr[1]
            hist = self.history[symbol]

            if len(hist) >= 10:  # Need minimum baseline
                tier = self.get_tier(symbol)
                tier_cfg = self.config.get("tiers", {}).get(tier, {}).get("volume_spike", {})
                z_thr = float(tier_cfg.get("z_thr", 4.0 if tier == "micro" else 5.0))
                k_req = int(tier_cfg.get("k", 3))

                arr = np.array(hist, dtype=float)
                med = float(np.median(arr))
                mad = float(np.median(np.abs(arr - med)))
                mad_floor = max(mad, 1e-9, 0.1 * med)

                z = 0.6745 * (finished_vol - med) / mad_floor

                if z >= z_thr:
                    self.consecutive_spikes[symbol] += 1
                else:
                    self.consecutive_spikes[symbol] = 0

                if self.consecutive_spikes[symbol] >= k_req:
                    # Check cooldown (30s)
                    last_t = self.last_fired.get(symbol, 0.0)
                    if ts - last_t >= 30.0:
                        self.last_fired[symbol] = ts
                        score = min(1.0, max(0.1, z / 12.0))
                        severity = self.map_severity(score)
                        ev_refs = [
                            EvidenceRef(kind="trade_id", ref=tid)
                            for tid in list(self.recent_trades[symbol])[-10:]
                        ]
                        if not ev_refs:
                            ev_refs = [EvidenceRef(kind="trade_id", ref=f"T-{symbol}-{int(ts)}")]

                        participants = list(set(self.recent_participants[symbol]))[:10]

                        now_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
                        start_iso = datetime.datetime.fromtimestamp(
                            max(0.0, ts - 60.0), tz=datetime.timezone.utc
                        ).isoformat()

                        anomalies.append(
                            AnomalyEvent(
                                schema_version="1.0.0",
                                anomaly_id=str(uuid.uuid4()),
                                type="VOLUME_SPIKE",
                                source_agent="quant_telemetry",
                                symbol=symbol,
                                window_start=start_iso,
                                window_end=now_iso,
                                score=round(score, 4),
                                severity=severity,
                                metrics={
                                    "z_score": round(z, 2),
                                    "volume": round(finished_vol, 2),
                                    "median_volume": round(med, 2),
                                    "mad": round(mad, 2),
                                    "consecutive_bins": self.consecutive_spikes[symbol],
                                    "tier": tier,
                                },
                                participants=participants,
                                evidence_refs=ev_refs,
                                detector_version=self.detector_version,
                                config_hash=self.config_hash,
                                detected_at=now_iso,
                            )
                        )

            hist.append(finished_vol)
            self.current_bins[symbol] = [bin_start, qty]
        else:
            # Same bin, accumulate
            curr[1] += qty

        return anomalies
