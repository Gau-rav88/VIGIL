from __future__ import annotations

import collections
import datetime
import uuid
from typing import Any

from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

from .base import Detector


class SpoofingLayeringDetector(Detector):
    """Detects spoofing / layering from L3 order events and trade executions."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        cfg = self.config.get("spoofing", {})
        self.window_s = float(cfg.get("window_ms", 2000)) / 1000.0
        self.min_orders = int(cfg.get("min_orders", 5))
        self.cancel_ratio_thr = float(cfg.get("cancel_ratio", 0.9))
        self.qty_mult = float(cfg.get("qty_mult", 5))

        # (symbol, account_id) -> deque of order actions: (ts, action, side, qty, order_id)
        self.order_history: dict[tuple[str, str], collections.deque[tuple[float, str, str, int, str]]] = (
            collections.defaultdict(lambda: collections.deque(maxlen=500))
        )
        # (symbol, account_id) -> deque of recent trades: (ts, side, qty, trade_id)
        self.trade_history: dict[tuple[str, str], collections.deque[tuple[float, str, int, str]]] = (
            collections.defaultdict(lambda: collections.deque(maxlen=200))
        )
        # symbol -> deque of order quantities to estimate median_order_qty
        self.order_qtys: dict[str, collections.deque[int]] = collections.defaultdict(
            lambda: collections.deque(maxlen=500)
        )
        self.last_fired: dict[tuple[str, str], float] = {}

    def on_event(self, event_type: str, data: dict[str, Any]) -> list[AnomalyEvent]:
        symbol = str(data.get("symbol", "UNKNOWN"))

        if event_type == "trade":
            ts = self.parse_ts(data.get("ts_exchange"))
            trade_id = str(data.get("trade_id", ""))
            qty = int(data.get("qty", 0))

            buyer = data.get("buyer", {}).get("account_id")
            seller = data.get("seller", {}).get("account_id")
            if buyer:
                self.trade_history[(symbol, buyer)].append((ts, "BUY", qty, trade_id))
            if seller:
                self.trade_history[(symbol, seller)].append((ts, "SELL", qty, trade_id))
            return []

        if event_type != "l3":
            return []

        ts = self.parse_ts(data.get("ts_exchange"))
        action = str(data.get("action", ""))
        side = str(data.get("side", ""))
        qty = int(data.get("qty", 0) or 0)
        order_id = str(data.get("order_id", ""))
        account_id = str(data.get("account_id", ""))

        if not account_id or action not in ("NEW", "CANCEL"):
            return []

        if action == "NEW" and qty > 0:
            self.order_qtys[symbol].append(qty)

        key = (symbol, account_id)
        history = self.order_history[key]
        history.append((ts, action, side, qty, order_id))

        cutoff = ts - self.window_s
        # Filter actions within the sliding window
        recent_actions = [a for a in history if a[0] >= cutoff]

        news = [a for a in recent_actions if a[1] == "NEW"]
        cancels = [a for a in recent_actions if a[1] == "CANCEL"]

        if not news:
            return []

        # Identify layered side (BUY or SELL)
        majority_side = "BUY" if sum(1 for a in news if a[2] == "BUY") >= (len(news) / 2) else "SELL"
        side_news = [a for a in news if a[2] == majority_side]
        side_cancels = [a for a in cancels if a[2] == majority_side]

        if len(side_news) < self.min_orders:
            return []

        cancel_ratio = len(side_cancels) / max(1, len(side_news))
        if cancel_ratio < self.cancel_ratio_thr:
            return []

        # Median order qty baseline
        sym_qtys = list(self.order_qtys[symbol])
        median_qty = (sum(sym_qtys) / len(sym_qtys)) if sym_qtys else 100.0
        sum_new_qty = sum(a[3] for a in side_news)

        if sum_new_qty < self.qty_mult * median_qty:
            return []

        # Check opposite-side trade within 1s after or during window
        opp_side = "SELL" if majority_side == "BUY" else "BUY"

        trades = self.trade_history[key]
        opp_trades = [t for t in trades if t[1] == opp_side and abs(t[0] - ts) <= 2.0]
        opp_exec = len(opp_trades) > 0

        # Fire anomaly if conditions met
        last_t = self.last_fired.get(key, 0.0)
        if ts - last_t >= 15.0:
            self.last_fired[key] = ts

            score = (
                0.4 * min(1.0, cancel_ratio)
                + 0.3 * min(1.0, sum_new_qty / (10.0 * max(1.0, median_qty)))
                + 0.3 * (1.0 if opp_exec else 0.5)
            )
            score = min(1.0, max(0.2, score))
            severity = self.map_severity(score)

            ev_refs = [
                EvidenceRef(kind="order_id", ref=a[4])
                for a in cancels[:5]
            ]
            for t in opp_trades[:2]:
                ev_refs.append(EvidenceRef(kind="trade_id", ref=t[3]))

            if not ev_refs:
                ev_refs = [EvidenceRef(kind="order_id", ref=order_id or f"O-{symbol}-{int(ts)}")]

            now_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
            start_iso = datetime.datetime.fromtimestamp(max(0.0, cutoff), tz=datetime.timezone.utc).isoformat()

            return [
                AnomalyEvent(
                    schema_version="1.0.0",
                    anomaly_id=str(uuid.uuid4()),
                    type="SPOOFING_LAYERING",
                    source_agent="quant_telemetry",
                    symbol=symbol,
                    window_start=start_iso,
                    window_end=now_iso,
                    score=round(score, 4),
                    severity=severity,
                    metrics={
                        "orders_new": len(news),
                        "cancels": len(cancels),
                        "cancel_ratio": round(cancel_ratio, 2),
                        "sum_new_qty": sum_new_qty,
                        "median_order_qty": round(median_qty, 1),
                        "opposite_execution": opp_exec,
                        "side": majority_side,
                    },
                    participants=[account_id],
                    evidence_refs=ev_refs,
                    detector_version=self.detector_version,
                    config_hash=self.config_hash,
                    detected_at=now_iso,
                )
            ]

        return []
