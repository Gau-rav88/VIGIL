"""Cross-correlation and permutation test (P4-T02, P4-T03).

FFT normalized xcorr for lags -120..+1800s, then circular block-shuffle
permutation test (B=500, block=60s) with seeded RNG for determinism.
"""
from __future__ import annotations

import hashlib

import numpy as np
import scipy.signal
from numpy.typing import NDArray

# Lag search window (seconds) — positive lag = social leads market
LAG_MIN_S = -120
LAG_MAX_S = 1800
# Permutation test parameters
PERM_BLOCK_S = 60
PERM_B_DEFAULT = 500
PERM_B_CASE_RUN = 1000


def normalized_xcorr(
    h: NDArray[np.float64],
    v: NDArray[np.float64],
    lag_min: int = LAG_MIN_S,
    lag_max: int = LAG_MAX_S,
) -> tuple[float, float]:
    """Compute FFT normalized cross-correlation between h (social) and v (market).

    Returns:
        best_lag_s: lag (seconds) where xcorr is maximised within [lag_min, lag_max]
        xcorr_peak: normalized xcorr value at best_lag_s

    Positive lag means social (h) leads market (v).
    """
    n = len(h)
    if n < 10:
        return 0.0, 0.0

    # Standardize
    h_std = _standardize(h)
    v_std = _standardize(v)

    # Full cross-correlation via FFT: correlate(v_std, h_std) gives:
    # corr[n - 1 + lag] = sum_t v[t] * h[t - lag]
    # When market reacts lag seconds AFTER social, lag > 0.
    corr = scipy.signal.correlate(v_std, h_std, mode="full", method="fft")

    # Divide by n (both already zero-mean, unit-variance)
    corr = corr / n

    # Map lags: offset = n-1 -> lag 0; offset 0 -> lag -(n-1)
    lags = np.arange(-(n - 1), n)

    # Restrict to requested lag window
    mask = (lags >= lag_min) & (lags <= lag_max)
    if not np.any(mask):
        return 0.0, 0.0

    sub_corr = corr[mask]
    sub_lags = lags[mask]

    best_idx = int(np.argmax(sub_corr))
    best_lag_s = float(sub_lags[best_idx])
    xcorr_peak = float(sub_corr[best_idx])
    return best_lag_s, xcorr_peak


def permutation_test(
    h: NDArray[np.float64],
    v: NDArray[np.float64],
    xcorr_observed: float,
    symbol: str,
    window_id: str,
    b: int = PERM_B_DEFAULT,
    block_s: int = PERM_BLOCK_S,
    lag_min: int = LAG_MIN_S,
    lag_max: int = LAG_MAX_S,
) -> float:
    """Circular block-shuffle permutation test.

    Args:
        h, v: time series arrays (already passed through xcorr to get observed stat)
        xcorr_observed: the observed max xcorr value
        symbol: ticker symbol (used for seeding RNG)
        window_id: e.g. ISO minute string (used for seeding RNG)
        b: number of permutation shuffles
        block_s: block length in seconds
        lag_min, lag_max: lag search window

    Returns:
        p_value = (1 + #{null_max >= xcorr_observed}) / (b + 1)
    """
    n = len(v)
    if n < 10:
        return 1.0

    # Seed RNG deterministically from (symbol, window_id) — NFR-INT-02
    seed_bytes = f"{symbol}:{window_id}".encode()
    seed_int = int(hashlib.sha256(seed_bytes).hexdigest(), 16) % (2**31)
    rng = np.random.default_rng(seed_int)

    v_std = _standardize(v)
    h_std = _standardize(h)

    # Number of full blocks
    n_blocks = max(1, n // block_s)
    usable_len = n_blocks * block_s
    v_blocks = v_std[:usable_len].reshape(n_blocks, block_s)
    h_usable = h_std[:usable_len]

    lags = np.arange(-(usable_len - 1), usable_len)
    lag_mask = (lags >= lag_min) & (lags <= lag_max)

    null_extremes: list[float] = []
    for _ in range(b):
        # Permute the 60s blocks
        shuffled_indices = rng.permutation(n_blocks)
        v_shuffled = v_blocks[shuffled_indices].ravel()

        corr = scipy.signal.correlate(v_shuffled, h_usable, mode="full", method="fft")
        corr = corr / usable_len
        sub_corr = corr[lag_mask]
        null_extremes.append(float(np.max(sub_corr)) if len(sub_corr) > 0 else 0.0)

    count_ge = sum(1 for x in null_extremes if x >= xcorr_observed)
    p_value = (1 + count_ge) / (b + 1)
    return p_value


def _standardize(arr: NDArray[np.float64]) -> NDArray[np.float64]:
    """Zero-mean, unit-std standardization."""
    mu = np.mean(arr)
    sigma = np.std(arr)
    if sigma < 1e-9:
        return arr - mu
    return (arr - mu) / sigma
