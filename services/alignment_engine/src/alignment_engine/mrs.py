"""Manipulation Risk Score (MRS) calculator (P4-T06).

Per-ticker per-minute formula from ARCHITECTURE.md §7.4:

    MRS = 100 × ( 0.30·hype/100
                + 0.25·min(1, volume_z/10)
                + 0.15·align            # xcorr_peak if p<0.01 else 0
                + 0.15·ring             # max ring_score of active cases for ticker, else 0
                + 0.10·price            # min(1, |ret_5m| / (5·σ_1h))
                + 0.05·micro )          # max score of SPREAD/DEPTH/SPOOFING anomalies in last 5 min

Component weights: must sum to 1.00; each component in [0, 1].
"""
from __future__ import annotations

from typing import Any

WEIGHT_HYPE = 0.30
WEIGHT_VOLUME = 0.25
WEIGHT_ALIGN = 0.15
WEIGHT_RING = 0.15
WEIGHT_PRICE = 0.10
WEIGHT_MICRO = 0.05

# Sanity check at import time
_TOTAL = WEIGHT_HYPE + WEIGHT_VOLUME + WEIGHT_ALIGN + WEIGHT_RING + WEIGHT_PRICE + WEIGHT_MICRO
assert abs(_TOTAL - 1.0) < 1e-9, f"MRS weights must sum to 1.0, got {_TOTAL}"

MICRO_ANOMALY_TYPES = frozenset({"SPREAD_WIDENING", "DEPTH_IMBALANCE", "SPOOFING_LAYERING"})


def compute_mrs(
    hype_score: float,
    volume_z: float,
    xcorr_peak: float,
    p_value: float,
    ring_score: float,
    ret_5m: float,
    sigma_1h: float,
    micro_score: float,
) -> tuple[float, dict[str, Any]]:
    """Compute MRS and return (mrs_value, components_dict).

    All input components are expected to be already-bounded raw values.
    The function clips each component to [0, 1] before weighting.

    Args:
        hype_score: current hype score (0-100 scale)
        volume_z: robust-z of 1-s volume (relative to recent baseline)
        xcorr_peak: normalized cross-correlation peak
        p_value: permutation test p-value (component is non-zero only if p<0.01)
        ring_score: max ring_score of active cases for this ticker (0 if none)
        ret_5m: 5-minute log return (signed)
        sigma_1h: 1-hour robust sigma of 1-min returns
        micro_score: max score of SPREAD/DEPTH/SPOOFING anomalies in last 5 min

    Returns:
        (mrs, components) where mrs ∈ [0, 100]
    """
    c_hype = float(max(0.0, min(1.0, hype_score / 100.0)))
    c_volume = float(max(0.0, min(1.0, volume_z / 10.0)))
    c_align = float(max(0.0, min(1.0, xcorr_peak))) if p_value < 0.01 else 0.0
    c_ring = float(max(0.0, min(1.0, ring_score)))
    price_denom = max(5.0 * sigma_1h, 1e-9)
    c_price = float(max(0.0, min(1.0, abs(ret_5m) / price_denom)))
    c_micro = float(max(0.0, min(1.0, micro_score)))

    mrs = 100.0 * (
        WEIGHT_HYPE * c_hype
        + WEIGHT_VOLUME * c_volume
        + WEIGHT_ALIGN * c_align
        + WEIGHT_RING * c_ring
        + WEIGHT_PRICE * c_price
        + WEIGHT_MICRO * c_micro
    )

    components = {
        "hype": c_hype,
        "volume": c_volume,
        "align": c_align,
        "ring": c_ring,
        "price": c_price,
        "micro": c_micro,
        "weights": {
            "hype": WEIGHT_HYPE,
            "volume": WEIGHT_VOLUME,
            "align": WEIGHT_ALIGN,
            "ring": WEIGHT_RING,
            "price": WEIGHT_PRICE,
            "micro": WEIGHT_MICRO,
        },
    }

    return float(max(0.0, min(100.0, mrs))), components
