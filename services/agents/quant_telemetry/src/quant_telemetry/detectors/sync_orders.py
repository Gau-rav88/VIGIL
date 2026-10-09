from __future__ import annotations

import collections
import datetime
import math
import uuid
from typing import Any

from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

from .base import Detector


class SynchronizedOrdersDetector(Detector):
    """Detects synchronized order placement across distinct accounts within 500ms bins."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        cfg = self.config.get("sync_orders", {})
        self.bin_s = float(cfg.get("bin_ms", 500)) / 1000.0
        self.min_accounts = int(cfg.get("min_accounts", 3))
        self.min_bins = int(cfg.get("min_bins", 3))
        self.window_s = float(cfg.get("window_s", 600))
        self.p_thr = float(cfg.get("p_thr", 0.01))

        # (symbol, side) -> bin_start_ts -> list of (account_id, order_id)
        self.bins: dict[tuple[str, str], dict[float, list[tuple[str, str]]]] = collections.defaultdict(dict)
        # (symbol, side) -> account_id -> order count in window
        self.account_counts: dict[tuple[str, str], collections.defaultdict[str, int]] = collections.defaultdict(
            lambda: collections.defaultdict(int)
        )
        self.last_fired: dict[tuple[str, str], float] = {}

    def on_event(self, event_type: str, data: dict[str, Any]) -> list[AnomalyEvent]:
        if event_type != "l3":
            return []

        action = str(data.get("action", ""))
        if action != "NEW":
            return []

        symbol = str(data.get("symbol", "UNKNOWN"))
        side = str(data.get("side", "BUY"))
        account_id = str(data.get("account_id", ""))
        order_id = str(data.get("order_id", ""))
        ts = self.parse_ts(data.get("ts_exchange"))

        if not account_id:
            return []

        key = (symbol, side)
        bin_ts = float(int(ts / self.bin_s) * self.bin_s)

        # Record into bin
        bin_dict = self.bins[key]
        if bin_ts not in bin_dict:
            bin_dict[bin_ts] = []
        bin_dict[bin_ts].append((account_id, order_id))
        self.account_counts[key][account_id] += 1

        # Prune old bins beyond window_s
        cutoff = ts - self.window_s
        stale_bins = [b for b in bin_dict if b < cutoff]
        for sb in stale_bins:
            for acc, _ in bin_dict[sb]:
                self.account_counts[key][acc] = max(0, self.account_counts[key][acc] - 1)
            del bin_dict[sb]

        # Check for synchronized bins
        current_entries = bin_dict[bin_ts]
        distinct_accs = list(dict.fromkeys(a[0] for a in current_entries))

        if len(distinct_accs) < self.min_accounts:
            return []

        # Find co-occurring account pairs across recent bins
        pair_counts: dict[tuple[str, str], list[str]] = collections.defaultdict(list)  # (a1, a2) -> list of order_ids
        pair_bin_counts: dict[tuple[str, str], int] = collections.defaultdict(int)

        for b_t, entries in bin_dict.items():
            b_accs = list(dict.fromkeys(e[0] for e in entries))
            if len(b_accs) >= self.min_accounts:
                for i in range(len(b_accs)):
                    for j in range(i + 1, len(b_accs)):
                        p: tuple[str, str] = (min(b_accs[i], b_accs[j]), max(b_accs[i], b_accs[j]))
                        pair_bin_counts[p] += 1
                        for e in entries:
                            if e[0] in p:
                                pair_counts[p].append(e[1])

        anomalies: list[AnomalyEvent] = []
        total_bins_in_win = max(1.0, self.window_s / self.bin_s)

        for pair, co_count in pair_bin_counts.items():
            if co_count >= self.min_bins:
                a1, a2 = pair
                c1 = self.account_counts[key][a1]
                c2 = self.account_counts[key][a2]

                # Lambda null rate per bin
                p1 = c1 / total_bins_in_win
                p2 = c2 / total_bins_in_win
                lam = max(1e-6, p1 * p2 * total_bins_in_win)

                # Poisson tail: P(X >= k)
                p_val = self._poisson_tail(lam, co_count)

                # Bonferroni correction over active pairs
                num_pairs = max(1, len(pair_bin_counts))
                adj_p = min(1.0, p_val * num_pairs)

                if adj_p < self.p_thr:
                    fire_key = (symbol, f"{a1}-{a2}")
                    last_t = self.last_fired.get(fire_key, 0.0)
                    if ts - last_t >= 30.0:
                        self.last_fired[fire_key] = ts
                        score = min(1.0, max(0.5, 1.0 - adj_p))
                        severity = self.map_severity(score)
                        ev_refs = [
                            EvidenceRef(kind="order_id", ref=oid)
                            for oid in list(dict.fromkeys(pair_counts[pair]))[:10]
                        ]
                        if not ev_refs:
                            ev_refs = [EvidenceRef(kind="order_id", ref=f"O-SYNC-{symbol}-{int(ts)}")]

                        now_iso = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
                        start_iso = datetime.datetime.fromtimestamp(
                            max(0.0, ts - 60.0), tz=datetime.timezone.utc
                        ).isoformat()

                        anomalies.append(
                            AnomalyEvent(
                                schema_version="1.0.0",
                                anomaly_id=str(uuid.uuid4()),
                                type="SYNCHRONIZED_ORDERS",
                                source_agent="quant_telemetry",
                                symbol=symbol,
                                window_start=start_iso,
                                window_end=now_iso,
                                score=round(score, 4),
                                severity=severity,
                                metrics={
                                    "co_bins": co_count,
                                    "p_val": round(adj_p, 6),
                                    "lambda": round(lam, 4),
                                    "side": side,
                                    "distinct_accounts_in_bin": len(distinct_accs),
                                },
                                participants=[a1, a2],
                                evidence_refs=ev_refs,
                                detector_version=self.detector_version,
                                config_hash=self.config_hash,
                                detected_at=now_iso,
                            )
                        )

        return anomalies

    @staticmethod
    def _poisson_tail(lam: float, k: int) -> float:
        """Compute P(X >= k) for Poisson(lam)."""
        if k <= 0:
            return 1.0
        # CDF sum_{i=0}^{k-1} lam^i * e^{-lam} / i!
        cdf = 0.0
        term = math.exp(-lam)
        cdf += term
        for i in range(1, k):
            term *= lam / i
            cdf += term
        return max(0.0, min(1.0, 1.0 - cdf))
