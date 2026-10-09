from __future__ import annotations

import collections
import datetime
import uuid
from typing import Any

from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

from .base import Detector


class WashCycleDetector(Detector):
    """Detects wash trading cycles, 2-cycles, and self-matched trades from market.trades.norm."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        cfg = self.config.get("wash_cycle", {})
        self.cycle_window_s = float(cfg.get("cycle_window_s", 900))
        self.qty_tol = float(cfg.get("qty_tol", 0.05))
        self.price_tol = float(cfg.get("price_tol", 0.005))
        self.max_len = int(cfg.get("max_len", 5))

        # symbol -> deque of trades: (ts, trade_id, seller, buyer, qty, price, seller_dev, buyer_dev)
        self.trade_windows: dict[str, collections.deque[tuple[float, str, str, str, int, float, str, str]]] = (
            collections.defaultdict(lambda: collections.deque(maxlen=2000))
        )
        self.last_fired: dict[tuple[str, str], float] = {}

    def on_event(self, event_type: str, data: dict[str, Any]) -> list[AnomalyEvent]:
        if event_type != "trade":
            return []

        symbol = str(data.get("symbol", "UNKNOWN"))
        ts = self.parse_ts(data.get("ts_exchange"))
        trade_id = str(data.get("trade_id", ""))
        price = float(data.get("price", 0.0))
        qty = int(data.get("qty", 0))

        buyer_obj = data.get("buyer") or {}
        seller_obj = data.get("seller") or {}
        buyer = str(buyer_obj.get("account_id", ""))
        seller = str(seller_obj.get("account_id", ""))
        buyer_dev = str(buyer_obj.get("device_fp", ""))
        seller_dev = str(seller_obj.get("device_fp", ""))

        if not buyer or not seller:
            return []

        window = self.trade_windows[symbol]
        # Prune old trades
        cutoff = ts - self.cycle_window_s
        while window and window[0][0] < cutoff:
            window.popleft()

        window.append((ts, trade_id, seller, buyer, qty, price, seller_dev, buyer_dev))

        anomalies: list[AnomalyEvent] = []

        # 1. Self-matched trade check
        if buyer == seller:
            anom = self._make_wash_anomaly(
                symbol=symbol,
                ts=ts,
                cycle_len=1,
                matched_qty=qty,
                price=price,
                participants=[buyer],
                evidence_trades=[trade_id],
                reason="SELF_MATCHED",
            )
            if anom:
                anomalies.append(anom)
                return anomalies

        # 2. Check 2-cycle (A <-> B)
        # Search backwards for a recent trade where seller=buyer and buyer=seller
        for past in reversed(list(window)[:-1]):
            p_ts, p_tid, p_seller, p_buyer, p_qty, p_price, _, _ = past
            if p_seller == buyer and p_buyer == seller:
                # Check quantity and price tolerance
                if abs(p_qty - qty) <= max(1, self.qty_tol * max(p_qty, qty)):
                    if abs(p_price - price) <= max(0.01, self.price_tol * max(p_price, price)):
                        anom = self._make_wash_anomaly(
                            symbol=symbol,
                            ts=ts,
                            cycle_len=2,
                            matched_qty=qty,
                            price=price,
                            participants=[seller, buyer],
                            evidence_trades=[p_tid, trade_id],
                            reason="2_CYCLE",
                        )
                        if anom:
                            anomalies.append(anom)
                            return anomalies
                        break

        # 3. Directed cycle DFS search (depth <= max_len)
        if len(window) >= 3:
            cycle = self._find_dfs_cycle(symbol, leading_seller=seller, current_buyer=buyer, target_qty=qty, target_price=price)
            if cycle:
                participants = [c[2] for c in cycle] + [c[3] for c in cycle] + [seller, buyer]
                tids = [c[1] for c in cycle] + [trade_id]
                anom = self._make_wash_anomaly(
                    symbol=symbol,
                    ts=ts,
                    cycle_len=len(cycle) + 1,
                    matched_qty=qty,
                    price=price,
                    participants=list(dict.fromkeys(participants)),
                    evidence_trades=tids,
                    reason=f"{len(cycle)+1}_CYCLE",
                )
                if anom:
                    anomalies.append(anom)

        return anomalies

    def _find_dfs_cycle(
        self,
        symbol: str,
        leading_seller: str,
        current_buyer: str,
        target_qty: int,
        target_price: float,
    ) -> list[tuple[float, str, str, str, int, float, str, str]] | None:
        """Find a path of trades from current_buyer back to leading_seller."""
        window = list(self.trade_windows[symbol])[:-1]
        # Build adjacency: account -> list of trades where account is seller
        adj: dict[str, list[tuple[float, str, str, str, int, float, str, str]]] = collections.defaultdict(list)
        for t in window:
            s_acc = t[2]
            # Match tolerance
            if abs(t[4] - target_qty) <= max(1, self.qty_tol * target_qty):
                if abs(t[5] - target_price) <= max(0.01, self.price_tol * target_price):
                    adj[s_acc].append(t)

        def dfs(curr_acc: str, path: list[tuple[float, str, str, str, int, float, str, str]], depth: int) -> list[tuple[float, str, str, str, int, float, str, str]] | None:
            if curr_acc == leading_seller and path:
                return path
            if len(path) >= self.max_len:
                return None
            for next_trade in adj.get(curr_acc, []):
                next_buyer = next_trade[3]
                if next_trade not in path:
                    res = dfs(next_buyer, path + [next_trade], depth + 1)
                    if res is not None:
                        return res
            return None

        return dfs(current_buyer, [], 1)

    def _make_wash_anomaly(
        self,
        symbol: str,
        ts: float,
        cycle_len: int,
        matched_qty: int,
        price: float,
        participants: list[str],
        evidence_trades: list[str],
        reason: str,
    ) -> AnomalyEvent | None:
        part_key = "-".join(sorted(participants))
        key = (symbol, part_key)
        last_t = self.last_fired.get(key, 0.0)
        if ts - last_t < 15.0:
            return None
        self.last_fired[key] = ts

        # Window total volume
        window_vol = sum(t[4] for t in self.trade_windows[symbol])
        vol_share = matched_qty / max(1.0, float(window_vol))

        score = min(1.0, max(0.5, 0.5 + 0.1 * cycle_len + 0.4 * vol_share))
        severity = self.map_severity(score)

        now_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
        start_iso = datetime.datetime.fromtimestamp(max(0.0, ts - 60.0), tz=datetime.timezone.utc).isoformat()

        return AnomalyEvent(
            schema_version="1.0.0",
            anomaly_id=str(uuid.uuid4()),
            type="WASH_CYCLE",
            source_agent="quant_telemetry",
            symbol=symbol,
            window_start=start_iso,
            window_end=now_iso,
            score=round(score, 4),
            severity=severity,
            metrics={
                "cycle_len": cycle_len,
                "matched_qty": matched_qty,
                "price": price,
                "pattern": reason,
                "volume_share": round(vol_share, 4),
            },
            participants=participants,
            evidence_refs=[EvidenceRef(kind="trade_id", ref=tid) for tid in evidence_trades],
            detector_version=self.detector_version,
            config_hash=self.config_hash,
            detected_at=now_iso,
        )
