from __future__ import annotations

from typing import Literal

from orchestrator.models import CaseState


def after_open(state: CaseState) -> Literal["enrich", "merged"]:
    if state.get("flags") and "MERGED" in state.get("flags", []):
        return "merged"
    return "enrich"


def after_enrich(state: CaseState) -> Literal["align", "failed"]:
    flags = state.get("flags", [])
    if "MISSING_MARKET_SLICE" in flags and "MISSING_SOCIAL_SLICE" in flags:
        return "failed"
    return "align"


def after_align(state: CaseState) -> Literal["attribute", "watchlist"]:
    flags = state.get("flags") or []
    if any(f in ("CIRCULAR_RING", "FINGERPRINT_CLUSTER", "COORDINATED_VOLUME_LOOP", "PUMP_AND_DUMP", "RING_TRIGGERED") for f in flags):
        return "attribute"
    align = state.get("alignment")
    if not align or align.get("status") == "NOT_RUN":
        return "attribute"  # proceed with fallback
    p_val = align.get("p_value", 0.0)
    peak = align.get("xcorr_peak", 0.0)
    # AC-ORC threshold
    if p_val < 0.01 and peak >= 0.50:
        return "attribute"
    # If alignment is weak, route to WATCHLIST
    return "watchlist"


def after_assess(state: CaseState) -> Literal["attribute", "draft", "close"]:
    conf = state.get("confidence") or {}
    overall = conf.get("overall", 0.85)
    window = state.get("window") or {}
    widen_count = window.get("widen_count", 0)

    if overall < 0.60 and widen_count < 2:
        return "attribute"
    if overall < 0.40:
        return "close"
    return "draft"


def after_validate(state: CaseState) -> Literal["sign", "draft"]:
    errors = state.get("errors") or []
    attempts = state.get("attempts") or {}
    val_attempts = attempts.get("validate", 0)
    if not errors:
        return "sign"
    if val_attempts <= 2:
        return "draft"
    # 3rd failure forces template mode and proceeds
    return "sign"


def after_sign(state: CaseState) -> Literal["await_review", "failed"]:
    if state.get("dossier_id"):
        return "await_review"
    return "failed"


def after_review(state: CaseState) -> Literal["publish", "rejected", "rework_attr", "rework_draft"]:
    rev = state.get("review") or {}
    status = rev.get("status", "NOT_REVIEWED")
    if status == "APPROVED":
        return "publish"
    if status == "REJECTED":
        return "rejected"
    if status == "REWORK":
        directives = state.get("directives") or []
        for d in directives:
            if d.get("type") in ("FORCE_REATTRIBUTION", "WIDEN_WINDOW", "EXCLUDE_ACCOUNT"):
                return "rework_attr"
        return "rework_draft"
    return "publish"
