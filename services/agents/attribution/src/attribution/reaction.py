from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import scipy.stats as stats


class ReactionLatencyAnalyzer:
    """
    Computes reaction latency between social CTA triggers and aggressive trader orders:
    - For each CTA timestamp t_c, latency = t_first_order_after(t_c) - t_c
    - Null distribution: 200 random reference times in the same window
    - One-sided Mann-Whitney U test (less)
    - Link if p < 0.01 and n >= 3
    """

    def __init__(self, n_ref_samples: int = 200, p_threshold: float = 0.01) -> None:
        self.n_ref_samples = n_ref_samples
        self.p_threshold = p_threshold

    def analyze_trader_reaction(
        self,
        cta_timestamps_ms: Sequence[int],
        trader_order_timestamps_ms: Sequence[int],
        window_start_ms: int,
        window_end_ms: int,
        rng: np.random.Generator | None = None,
    ) -> dict[str, Any] | None:
        if len(cta_timestamps_ms) < 3 or len(trader_order_timestamps_ms) < 3:
            return None

        # Sorted order timestamps
        orders = sorted(trader_order_timestamps_ms)

        # 1. Measure latencies to first order after each CTA
        trader_latencies: list[float] = []
        for t_c in cta_timestamps_ms:
            # Find first order >= t_c
            idx = np.searchsorted(orders, t_c)
            if idx < len(orders):
                diff_s = (orders[idx] - t_c) / 1000.0
                if 0.0 <= diff_s <= 600.0:  # Within 10 min window
                    trader_latencies.append(diff_s)

        if len(trader_latencies) < 3:
            return None

        # 2. Build null distribution from random reference times
        _rng = rng or np.random.default_rng(42)
        ref_times = _rng.uniform(window_start_ms, window_end_ms, size=self.n_ref_samples)

        ref_latencies: list[float] = []
        for t_ref in ref_times:
            idx = np.searchsorted(orders, t_ref)
            if idx < len(orders):
                diff_s = (orders[idx] - t_ref) / 1000.0
                if 0.0 <= diff_s <= 600.0:
                    ref_latencies.append(diff_s)

        if len(ref_latencies) < 20:
            return None

        # 3. Mann-Whitney U test
        res = stats.mannwhitneyu(trader_latencies, ref_latencies, alternative="less")
        p_val = float(res.pvalue)

        if p_val < self.p_threshold:
            confidence = max(0.60, min(0.99, 1.0 - p_val))
            return {
                "p_value": p_val,
                "confidence": confidence,
                "n_reactions": len(trader_latencies),
                "median_latency_s": float(np.median(trader_latencies)),
                "null_median_latency_s": float(np.median(ref_latencies)),
            }

        return None
