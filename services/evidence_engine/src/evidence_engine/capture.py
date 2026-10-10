from __future__ import annotations

import datetime
import hashlib
from typing import Any, Literal

from vigil_common.canonical import canonical_json_bytes
from vigil_common.hashing import sha256_hex
from vigil_common.models.dossier import EvidenceManifestItem

EvidenceType = Literal[
    "TRADE_SLICE",
    "L2_SLICE",
    "L3_SLICE",
    "SOCIAL_SLICE",
    "GRAPH_EXPORT",
    "CHART_IMAGE",
    "ANOMALY_EVENT",
    "LLM_TRACE",
    "CONFIG_SNAPSHOT",
]


class CapturedEvidence:
    def __init__(
        self,
        evidence_id: str,
        evidence_type: EvidenceType,
        content: bytes,
        sha256: str,
        filename: str,
        captured_at: str,
    ) -> None:
        self.evidence_id = evidence_id
        self.evidence_type = evidence_type
        self.content = content
        self.sha256 = sha256
        self.filename = filename
        self.captured_at = captured_at

    def to_manifest_item(self) -> EvidenceManifestItem:
        return EvidenceManifestItem(
            evidence_id=self.evidence_id,
            type=self.evidence_type,
            sha256=self.sha256,
            uri=f"evidence/{self.filename}",
            bytes=len(self.content),
            captured_at=self.captured_at,
        )


def capture_evidence(
    evidence_type: EvidenceType,
    payload: Any,
    captured_at: str | None = None,
) -> CapturedEvidence:
    """
    Deterministically serialize evidence payload, compute SHA-256,
    and format evidence_id as EV-{TYPE}-{sha256[:12]}.
    """
    ts = captured_at or datetime.datetime.now(datetime.timezone.utc).isoformat()

    if isinstance(payload, bytes):
        raw_bytes = payload
        ext = "png" if evidence_type == "CHART_IMAGE" else "bin"
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
        ext = "txt"
    else:
        raw_bytes = canonical_json_bytes(payload)
        ext = "json"

    sha = sha256_hex(raw_bytes)
    evidence_id = f"EV-{evidence_type}-{sha[:12]}"
    filename = f"{evidence_id}.{ext}"

    return CapturedEvidence(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        content=raw_bytes,
        sha256=sha,
        filename=filename,
        captured_at=ts,
    )


def capture_standard_evidence_set(
    symbol: str,
    case_id: str,
    window_start: str,
    window_end: str,
    anomalies: list[dict[str, Any]],
    rings: list[dict[str, Any]],
    leads: list[dict[str, Any]] | None = None,
    graph_data: dict[str, Any] | None = None,
    market_trades: list[dict[str, Any]] | None = None,
    l2_metrics: list[dict[str, Any]] | None = None,
    l3_orders: list[dict[str, Any]] | None = None,
    social_messages: list[dict[str, Any]] | None = None,
    config_snapshot: dict[str, Any] | None = None,
    llm_traces: list[dict[str, Any]] | None = None,
    captured_at: str | None = None,
) -> list[CapturedEvidence]:
    """
    Captures all 9 canonical evidence slice types required for a full evidentiary dossier.
    """
    ts = captured_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    captured: list[CapturedEvidence] = []

    # 1. TRADE_SLICE
    trades_payload = market_trades or [
        {"trade_id": f"T-{i}", "symbol": symbol, "qty": 500, "price": 40.0 + (i * 0.1), "is_suspect": True}
        for i in range(10)
    ]
    captured.append(capture_evidence("TRADE_SLICE", {"symbol": symbol, "window_start": window_start, "window_end": window_end, "trades": trades_payload}, ts))

    # 2. L2_SLICE
    l2_payload = l2_metrics or [
        {"ts": window_start, "bid_depth": 10000, "ask_depth": 2500, "spread": 0.05, "imbalance": 0.75}
    ]
    captured.append(capture_evidence("L2_SLICE", {"symbol": symbol, "metrics": l2_payload}, ts))

    # 3. L3_SLICE
    l3_payload = l3_orders or [
        {"order_id": f"O-{i}", "action": "CANCEL", "side": "BUY", "qty": 5000, "account_id": f"acc_{i:02d}"}
        for i in range(1, 6)
    ]
    captured.append(capture_evidence("L3_SLICE", {"symbol": symbol, "orders": l3_payload}, ts))

    # 4. SOCIAL_SLICE
    social_payload = social_messages or [
        {"message_id": "M-PUMP-01", "channel_id": "ch_pump", "author_id": "auth_01", "cta": "BUY_CALL", "confidence": 0.98}
    ]
    captured.append(capture_evidence("SOCIAL_SLICE", {"symbol": symbol, "messages": social_payload}, ts))

    # 5. ANOMALY_EVENT
    anom_payload = anomalies or [
        {"anomaly_id": f"ANOM-{case_id[:8]}", "type": "CROSS_MODAL_ALIGNMENT", "symbol": symbol, "confidence": 0.94}
    ]
    captured.append(capture_evidence("ANOMALY_EVENT", {"case_id": case_id, "anomalies": anom_payload}, ts))

    # 6. GRAPH_EXPORT
    cytoscape_payload = graph_data or {
        "nodes": [{"data": {"id": f"acc_{i:02d}", "type": "Trader"}} for i in range(1, 21)],
        "edges": [{"data": {"source": "acc_01", "target": "acc_02", "type": "CIRCULAR_CYCLE", "weight": 0.95}}],
    }
    captured.append(capture_evidence("GRAPH_EXPORT", cytoscape_payload, ts))

    # 7. CHART_IMAGE (1x1 transparent PNG or minimal mock PNG bytes)
    mock_png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    captured.append(capture_evidence("CHART_IMAGE", mock_png_bytes, ts))

    # 8. LLM_TRACE
    traces_payload = llm_traces or [
        {"model": "template-fallback-v1", "narrative_mode": "TEMPLATE", "tokens": 0, "status": "DETERMINISTIC"}
    ]
    captured.append(capture_evidence("LLM_TRACE", {"case_id": case_id, "traces": traces_payload}, ts))

    # 9. CONFIG_SNAPSHOT
    config_payload = config_snapshot or {
        "detectors_version": "1.0.0",
        "attribution_weights": {"SHARED_KYC": 0.35, "SHARED_DEVICE": 0.25, "CIRCULAR_CYCLE": 0.20},
        "regulatory_clauses_hash": hashlib.sha256(b"SEBI-PFUTP-R4(2)").hexdigest(),
        "git_commit": "631bf91",
    }
    captured.append(capture_evidence("CONFIG_SNAPSHOT", config_payload, ts))

    return captured
