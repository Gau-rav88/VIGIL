"""Series assembly for cross-modal alignment (P4-T01, P4-T05).

Builds 1-second grid arrays for:
- h(t): hype score from hype_scores table
- v(t): volume robust-z (log1p, detrended by 5-min rolling median)
- a(t): absolute 1-s log return
- spread_rel(t): relative spread from l2_metrics_1s
"""
from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    import asyncpg

# Configuration from env with documented defaults
ALIGN_LOOKBACK_S = int(os.getenv("ALIGN_LOOKBACK_S", "1800"))
ALIGN_INTERVAL_S = int(os.getenv("ALIGN_INTERVAL_S", "60"))
ALIGN_MIN_OBS = int(os.getenv("ALIGN_MIN_OBS", "30"))
WATERMARK_S = 30
DETREND_WINDOW_S = 300


async def fetch_series(
    conn: "asyncpg.Connection[asyncpg.Record]",
    symbol: str,
    now_ts: float,
    lookback_s: int = ALIGN_LOOKBACK_S,
    min_obs: int = ALIGN_MIN_OBS,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], bool]:
    """Fetch h, v, a, spread_rel as 1-s grid arrays over [now_ts - lookback_s, now_ts].

    Returns four arrays of length `lookback_s`, each indexed t=0 (oldest) … t=n-1 (newest),
    along with `is_sufficient` boolean indicating whether both h and v have at least min_obs
    non-empty observations with non-zero variance.
    """
    t_start = now_ts - lookback_s - WATERMARK_S  # allow late data within watermark
    t_end = now_ts
    n = lookback_s

    # ---- hype scores ----
    h = np.zeros(n, dtype=np.float64)
    rows_hype = await conn.fetch(
        """
        SELECT EXTRACT(EPOCH FROM ts)::double precision AS ts_s, hype_score
        FROM vigil.hype_scores
        WHERE ticker = $1
          AND ts >= to_timestamp($2)
          AND ts <  to_timestamp($3)
        ORDER BY ts
        """,
        symbol,
        t_start,
        t_end,
    )
    for row in rows_hype:
        idx = int(row["ts_s"] - (t_end - lookback_s))
        if 0 <= idx < n:
            h[idx] = float(row["hype_score"])
    _ffill(h)

    # ---- bars_1s: volume (qty) and price for v(t) and a(t) ----
    v_raw = np.zeros(n, dtype=np.float64)
    price_arr = np.full(n, np.nan)
    rows_trades = await conn.fetch(
        """
        SELECT
            date_trunc('second', ts) AS bar_ts,
            SUM(qty)::double precision AS vol,
            (ARRAY_AGG(price ORDER BY ts DESC))[1]::double precision AS last_price
        FROM vigil.trades
        WHERE symbol = $1
          AND ts >= to_timestamp($2)
          AND ts <  to_timestamp($3)
        GROUP BY bar_ts
        ORDER BY bar_ts
        """,
        symbol,
        t_start,
        t_end,
    )
    for row in rows_trades:
        bar_ts: datetime.datetime = row["bar_ts"]
        idx = int(bar_ts.timestamp() - (t_end - lookback_s))
        if 0 <= idx < n:
            v_raw[idx] = float(row["vol"])
            price_arr[idx] = float(row["last_price"])

    # --- log1p volume and detrend by 5-min rolling median ---
    v_log = np.log1p(v_raw)
    v = _detrend_rolling_median(v_log, DETREND_WINDOW_S)

    # --- absolute 1-s log return ---
    a = np.zeros(n, dtype=np.float64)
    # Forward-fill prices first
    _ffill_nan(price_arr)
    if not np.all(np.isnan(price_arr)):
        log_px = np.where(price_arr > 0, np.log(np.maximum(price_arr, 1e-9)), np.nan)
        _ffill_nan(log_px)
        ret = np.diff(log_px, prepend=log_px[0])
        a = np.abs(ret)

    # ---- spread_rel from l2_metrics_1s ----
    spread_rel = np.zeros(n, dtype=np.float64)
    rows_l2 = await conn.fetch(
        """
        SELECT EXTRACT(EPOCH FROM ts)::double precision AS ts_s, rel_spread
        FROM vigil.l2_metrics_1s
        WHERE symbol = $1
          AND ts >= to_timestamp($2)
          AND ts <  to_timestamp($3)
        ORDER BY ts
        """,
        symbol,
        t_start,
        t_end,
    )
    for row in rows_l2:
        idx = int(row["ts_s"] - (t_end - lookback_s))
        if 0 <= idx < n:
            v_val = row["rel_spread"]
            if v_val is not None:
                spread_rel[idx] = float(v_val)

    h_obs = int(np.count_nonzero(h))
    v_obs = int(np.count_nonzero(v_raw))
    h_var = float(np.var(h))
    v_var = float(np.var(v_raw))
    is_sufficient = bool(h_obs >= min_obs and v_obs >= min_obs and h_var > 1e-9 and v_var > 1e-9)

    return h, v, a, spread_rel, is_sufficient


def _ffill(arr: NDArray[np.float64]) -> None:
    """Forward-fill zeros in place (simple version)."""
    last = 0.0
    for i in range(len(arr)):
        if arr[i] != 0.0:
            last = arr[i]
        else:
            arr[i] = last


def _ffill_nan(arr: NDArray[np.float64]) -> None:
    """Forward-fill NaNs in place."""
    last = 0.0
    for i in range(len(arr)):
        if not np.isnan(arr[i]):
            last = arr[i]
        else:
            arr[i] = last


def _detrend_rolling_median(arr: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """Subtract 5-min rolling median then robust-z normalise."""
    n = len(arr)
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        start = max(0, i - window + 1)
        med = np.median(arr[start : i + 1])
        out[i] = arr[i] - med
    # Robust-z: divide by MAD * 1.4826, fall back to sample std if MAD is 0 on sparse data
    mad = np.median(np.abs(out - np.median(out)))
    sigma = mad * 1.4826 if mad > 1e-4 else max(float(np.std(out)), 1e-4)
    res: NDArray[np.float64] = np.asarray(out / sigma, dtype=np.float64)
    return res
