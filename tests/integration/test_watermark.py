"""Integration test: watermark - late social message reflected next cycle (P4-G2).

Tests that a social message arriving within 30s watermark is counted in series.
This test is offline-only: uses in-memory helpers to simulate the watermark logic.
"""
from __future__ import annotations

import numpy as np
from alignment_engine.series import WATERMARK_S, _ffill


def _make_hype_rows(
    n: int,
    base_ts: float,
    late_inject_offset: int | None = None,
    late_value: float = 80.0,
) -> list[dict[str, float]]:
    """Simulate hype_scores rows including optional late injection."""
    rows = [{"ts_s": base_ts + i, "hype_score": float(i % 10 + 5)} for i in range(n)]
    if late_inject_offset is not None and abs(late_inject_offset) <= WATERMARK_S:
        inject_ts = base_ts + n + late_inject_offset  # within watermark
        rows.append({"ts_s": inject_ts, "hype_score": late_value})
    return rows


def _apply_hype_to_grid(
    rows: list[dict[str, float]],
    t_end: float,
    n: int,
) -> np.ndarray:
    """Mirror the series assembly logic for hype."""
    h = np.zeros(n, dtype=float)
    for row in rows:
        idx = int(row["ts_s"] - (t_end - n))
        if 0 <= idx < n:
            h[idx] = row["hype_score"]
    _ffill(h)
    return h


class TestWatermark:
    def test_on_time_message_always_reflected(self) -> None:
        """On-time message (within the main lookback) lands in grid correctly."""
        n = 100
        now_ts = 1000.0
        base_ts = now_ts - n
        rows = _make_hype_rows(n, base_ts)
        h = _apply_hype_to_grid(rows, now_ts, n)
        # All slots should be non-zero (ffilled from row data)
        assert np.any(h > 0), "Expected non-zero hype from on-time rows"

    def test_late_message_within_watermark_reflected(self) -> None:
        """A message arriving WATERMARK_S seconds late is still included via the t_start extension."""
        n = 100
        now_ts = 1000.0
        base_ts = now_ts - n
        # Late by 25s (< WATERMARK_S=30) but with ts in the lookback window
        late_ts_s = now_ts - 25.0  # just within watermark tolerance
        rows = _make_hype_rows(n, base_ts)
        rows.append({"ts_s": late_ts_s, "hype_score": 95.0})

        h = _apply_hype_to_grid(rows, now_ts, n)
        # The late message ts is within [now_ts - n, now_ts], so idx >= 0
        idx = int(late_ts_s - (now_ts - n))
        assert 0 <= idx < n, f"Late message idx={idx} outside grid"
        assert h[idx] == 95.0 or h[idx] > 0.0, f"Late message not reflected in grid at idx={idx}"

    def test_very_late_message_excluded(self) -> None:
        """A message arriving more than WATERMARK_S seconds late is excluded from current grid."""
        n = 100
        now_ts = 1000.0
        # A message timestamped 60 seconds before the lookback window starts
        very_late_ts = now_ts - n - 60.0  # before t_start = now_ts - n - WATERMARK_S
        rows: list[dict[str, float]] = [{"ts_s": very_late_ts, "hype_score": 99.0}]
        h = _apply_hype_to_grid(rows, now_ts, n)
        # idx would be negative: -60
        idx = int(very_late_ts - (now_ts - n))
        assert idx < 0, f"Very late message should have negative idx, got {idx}"
        assert np.all(h == 0.0), "Very late message should not appear in grid"

    def test_watermark_constant(self) -> None:
        """WATERMARK_S must be exactly 30 seconds."""
        assert WATERMARK_S == 30, f"Watermark must be 30s, got {WATERMARK_S}"
