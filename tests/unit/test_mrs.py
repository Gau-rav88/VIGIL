"""Unit tests for MRS component weights and bounds (P4-G3)."""
from __future__ import annotations

from alignment_engine.mrs import (
    WEIGHT_ALIGN,
    WEIGHT_HYPE,
    WEIGHT_MICRO,
    WEIGHT_PRICE,
    WEIGHT_RING,
    WEIGHT_VOLUME,
    compute_mrs,
)


def test_weights_sum_to_one() -> None:
    total = WEIGHT_HYPE + WEIGHT_VOLUME + WEIGHT_ALIGN + WEIGHT_RING + WEIGHT_PRICE + WEIGHT_MICRO
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


def test_components_in_range() -> None:
    mrs, comp = compute_mrs(
        hype_score=80.0,
        volume_z=5.0,
        xcorr_peak=0.7,
        p_value=0.005,
        ring_score=0.4,
        ret_5m=0.02,
        sigma_1h=0.005,
        micro_score=0.6,
    )
    for key in ("hype", "volume", "align", "ring", "price", "micro"):
        val = comp[key]
        assert 0.0 <= val <= 1.0, f"Component '{key}' = {val} not in [0, 1]"


def test_mrs_in_range() -> None:
    for hype in [0.0, 50.0, 100.0]:
        for volume_z in [0.0, 5.0, 15.0]:
            mrs, _ = compute_mrs(
                hype_score=hype,
                volume_z=volume_z,
                xcorr_peak=0.5,
                p_value=0.005,
                ring_score=0.5,
                ret_5m=0.01,
                sigma_1h=0.004,
                micro_score=0.3,
            )
            assert 0.0 <= mrs <= 100.0, f"MRS={mrs} out of [0, 100] for hype={hype}, vol_z={volume_z}"


def test_align_zero_when_p_not_significant() -> None:
    """align component must be 0 when p_value >= 0.01."""
    _, comp_ns = compute_mrs(
        hype_score=0.0,
        volume_z=0.0,
        xcorr_peak=0.9,  # strong xcorr
        p_value=0.05,    # NOT significant
        ring_score=0.0,
        ret_5m=0.0,
        sigma_1h=1.0,
        micro_score=0.0,
    )
    assert comp_ns["align"] == 0.0, f"align should be 0 when p>=0.01, got {comp_ns['align']}"

    _, comp_sig = compute_mrs(
        hype_score=0.0,
        volume_z=0.0,
        xcorr_peak=0.9,  # strong xcorr
        p_value=0.005,   # significant
        ring_score=0.0,
        ret_5m=0.0,
        sigma_1h=1.0,
        micro_score=0.0,
    )
    assert comp_sig["align"] > 0.0, "align should be non-zero when p<0.01"


def test_mrs_max_scenario() -> None:
    """All-max inputs should produce MRS near 100."""
    mrs, _ = compute_mrs(
        hype_score=100.0,
        volume_z=10.0,
        xcorr_peak=1.0,
        p_value=0.001,
        ring_score=1.0,
        ret_5m=1.0,    # very large return
        sigma_1h=0.001,  # tiny sigma → large ratio
        micro_score=1.0,
    )
    assert mrs > 90.0, f"All-max MRS should be >90, got {mrs}"


def test_mrs_zero_scenario() -> None:
    """All-zero inputs should produce MRS = 0."""
    mrs, comp = compute_mrs(
        hype_score=0.0,
        volume_z=0.0,
        xcorr_peak=0.0,
        p_value=1.0,     # not significant
        ring_score=0.0,
        ret_5m=0.0,
        sigma_1h=1.0,
        micro_score=0.0,
    )
    assert mrs == 0.0, f"All-zero MRS should be 0.0, got {mrs}"
    for key in ("hype", "volume", "align", "ring", "price", "micro"):
        assert comp[key] == 0.0, f"Component {key} should be 0.0 for all-zero inputs"
