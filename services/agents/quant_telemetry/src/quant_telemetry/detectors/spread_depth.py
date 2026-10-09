from __future__ import annotations

import collections
import datetime
import statistics
import uuid
from typing import Any

from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

from .base import Detector


class SpreadDepthDetector(Detector):
    """Detects SPREAD_WIDENING and DEPTH_IMBALANCE from L2 snapshots."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        cfg = self.config.get("spread_depth", {})
        self.spread_mult = float(cfg.get("spread_mult", 3.0))
        self.imbalance_thr = float(cfg.get("imbalance_thr", 0.7))
        self.imbalance_hold_s = float(cfg.get("imbalance_hold_s", 10.0))

        # symbol -> deque of past spreads over 15 min
        self.spread_history: dict[str, collections.deque[float]] = collections.defaultdict(
            lambda: collections.deque(maxlen=900)
        )
        # symbol -> [first_high_imbalance_ts, last_high_imbalance_ts, last_imbalance_val]
        self.imbalance_tracker: dict[str, list[float]] = {}
        self.last_fired_spread: dict[str, float] = {}
        self.last_fired_depth: dict[str, float] = {}

    def on_event(self, event_type: str, data: dict[str, Any]) -> list[AnomalyEvent]:
        if event_type != "l2":
            return []

        symbol = str(data.get("symbol", "UNKNOWN"))
        ts = self.parse_ts(data.get("ts_exchange"))
        seq = int(data.get("seq", 0))

        bids = data.get("bids", [])
        asks = data.get("asks", [])
        if not bids or not asks:
            return []

        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid = (best_bid + best_ask) / 2.0
        if mid <= 0:
            return []

        rel_spread = (best_ask - best_bid) / mid
        spread_hist = self.spread_history[symbol]

        anomalies: list[AnomalyEvent] = []

        # 1. Spread Widening Check
        if len(spread_hist) >= 20:
            med_spread = float(statistics.median(spread_hist))
            if med_spread > 0 and rel_spread >= self.spread_mult * med_spread:
                last_t = self.last_fired_spread.get(symbol, 0.0)
                if ts - last_t >= 30.0:
                    self.last_fired_spread[symbol] = ts
                    score = min(1.0, max(0.1, rel_spread / (6.0 * max(1e-6, med_spread))))
                    severity = self.map_severity(score)
                    now_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
                    start_iso = datetime.datetime.fromtimestamp(
                        max(0.0, ts - 60.0), tz=datetime.timezone.utc
                    ).isoformat()

                    anomalies.append(
                        AnomalyEvent(
                            schema_version="1.0.0",
                            anomaly_id=str(uuid.uuid4()),
                            type="SPREAD_WIDENING",
                            source_agent="quant_telemetry",
                            symbol=symbol,
                            window_start=start_iso,
                            window_end=now_iso,
                            score=round(score, 4),
                            severity=severity,
                            metrics={
                                "rel_spread": round(rel_spread, 6),
                                "median_spread": round(med_spread, 6),
                                "spread_mult": round(rel_spread / med_spread, 2),
                                "best_bid": best_bid,
                                "best_ask": best_ask,
                            },
                            participants=[],
                            evidence_refs=[EvidenceRef(kind="l2_seq", ref=str(seq))],
                            detector_version=self.detector_version,
                            config_hash=self.config_hash,
                            detected_at=now_iso,
                        )
                    )

        spread_hist.append(rel_spread)

        # 2. Depth Imbalance Check (top 5 levels)
        top_bids = bids[:5]
        top_asks = asks[:5]
        sum_bid_qty = sum(float(b[1]) for b in top_bids)
        sum_ask_qty = sum(float(a[1]) for a in top_asks)
        total_depth = sum_bid_qty + sum_ask_qty

        if total_depth > 0:
            imbalance = (sum_bid_qty - sum_ask_qty) / total_depth
            abs_imb = abs(imbalance)

            tracker = self.imbalance_tracker.get(symbol)
            if abs_imb >= self.imbalance_thr:
                if tracker is None:
                    self.imbalance_tracker[symbol] = [ts, ts, imbalance]
                else:
                    tracker[1] = ts
                    tracker[2] = imbalance
                    hold_duration = tracker[1] - tracker[0]
                    if hold_duration >= self.imbalance_hold_s:
                        last_t = self.last_fired_depth.get(symbol, 0.0)
                        if ts - last_t >= 30.0:
                            self.last_fired_depth[symbol] = ts
                            score = min(1.0, max(0.1, abs_imb))
                            severity = self.map_severity(score)
                            now_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
                            start_iso = datetime.datetime.fromtimestamp(
                                max(0.0, ts - hold_duration), tz=datetime.timezone.utc
                            ).isoformat()

                            anomalies.append(
                                AnomalyEvent(
                                    schema_version="1.0.0",
                                    anomaly_id=str(uuid.uuid4()),
                                    type="DEPTH_IMBALANCE",
                                    source_agent="quant_telemetry",
                                    symbol=symbol,
                                    window_start=start_iso,
                                    window_end=now_iso,
                                    score=round(score, 4),
                                    severity=severity,
                                    metrics={
                                        "imbalance": round(imbalance, 4),
                                        "hold_seconds": round(hold_duration, 1),
                                        "sum_bid_qty": sum_bid_qty,
                                        "sum_ask_qty": sum_ask_qty,
                                    },
                                    participants=[],
                                    evidence_refs=[EvidenceRef(kind="l2_seq", ref=str(seq))],
                                    detector_version=self.detector_version,
                                    config_hash=self.config_hash,
                                    detected_at=now_iso,
                                )
                            )
            else:
                self.imbalance_tracker.pop(symbol, None)

        return anomalies
