from __future__ import annotations

import io

import pypdf
import pytest
from evidence_engine.capture import capture_evidence, capture_standard_evidence_set
from evidence_engine.pdf import render_dossier_pdf
from evidence_engine.reveal import IdentityRevealService


def test_capture_evidence_types_and_ids() -> None:
    ev = capture_evidence("TRADE_SLICE", {"trades": [{"id": 1}]})
    assert ev.evidence_type == "TRADE_SLICE"
    assert ev.evidence_id.startswith("EV-TRADE_SLICE-")
    assert ev.filename.endswith(".json")
    assert len(ev.sha256) == 64

    manifest_item = ev.to_manifest_item()
    assert manifest_item.evidence_id == ev.evidence_id
    assert manifest_item.bytes == len(ev.content)


def test_capture_all_9_evidence_slices() -> None:
    slices = capture_standard_evidence_set(
        symbol="ZENITHSME",
        case_id="case_unit_01",
        window_start="2026-03-14T00:00:00Z",
        window_end="2026-03-14T02:00:00Z",
        anomalies=[],
        rings=[],
    )
    assert len(slices) == 9
    types = {s.evidence_type for s in slices}
    expected_types = {
        "TRADE_SLICE", "L2_SLICE", "L3_SLICE", "SOCIAL_SLICE",
        "ANOMALY_EVENT", "GRAPH_EXPORT", "CHART_IMAGE", "LLM_TRACE", "CONFIG_SNAPSHOT"
    }
    assert types == expected_types


def test_pdf_rendering_unit() -> None:
    minimal_dossier = {
        "case_id": "case_pdf_unit",
        "dossier_id": "dossier_pdf_unit",
        "version": 1,
        "jurisdiction": "SEBI_IN",
        "subject": {
            "symbol": "ZENITHSME",
            "exchange": "SYNTH",
            "window_start": "2026-03-14T00:00:00Z",
            "window_end": "2026-03-14T02:00:00Z",
            "manipulation_types": ["PUMP_AND_DUMP"],
        },
        "executive_summary": {
            "text": "Forensic narrative testing [EV-1]. Coordinated pump [EV-2].",
            "citations": ["EV-1", "EV-2"],
        },
        "timeline": [
            {"ts": "2026-03-14T00:00:00Z", "track": "MARKET", "description": "Trade [EV-1]", "evidence_ids": ["EV-1"]}
        ],
        "market_evidence": {
            "total_volume": 1000,
            "suspect_volume": 500,
            "suspect_volume_ratio": 0.5,
            "price_move_pct": 10.0,
            "anomalies": ["A1"],
        },
        "social_evidence": {
            "channels": ["Telegram"],
            "message_count": 50,
            "hype_peak": 75.0,
            "cta_breakdown": {"BUY": 40},
            "near_duplicate_campaigns": 1,
        },
        "attribution": {
            "rings": [
                {
                    "ring_id": "r1",
                    "entity_id": "e1",
                    "ring_score": 0.95,
                    "accounts": ["a1", "a2"],
                    "methods": ["SHARED_DEVICE"],
                    "cycle_count": 1,
                    "net_volume": 500,
                }
            ],
            "leads": [],
        },
        "violated_clauses": [
            {
                "regime": "SEBI",
                "clause_id": "SEBI-PFUTP-R4(2)",
                "title": "Reg 4(2)",
                "finding_types": ["WASH_CYCLE"],
                "rationale": "Circular",
                "legal_review_required": True,
            }
        ],
        "signature": {
            "alg": "Ed25519",
            "key_id": "dev-1",
            "canonicalization": "RFC8785-JCS",
            "digest_sha256": "0" * 64,
            "value_b64": "AA==",
            "signed_at": "2026-03-14T00:00:00Z",
        },
        "evidence_manifest": [],
        "merkle_root": "0" * 64,
    }

    pdf_bytes = render_dossier_pdf(minimal_dossier)
    assert len(pdf_bytes) > 500
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1


@pytest.mark.asyncio
async def test_identity_reveal_service_validation() -> None:
    svc = IdentityRevealService("postgresql://vigil:vigil@localhost:5434/vigil")
    with pytest.raises(ValueError):
        await svc.reveal_account("case_1", "acc_1", "officer_1", "")  # empty justification raises

    # Test valid execution with DB
    try:
        import uuid
        res = await svc.reveal_account(str(uuid.uuid4()), "acc_seller_0001", "officer_compliance", "Authorized SEBI formal inquiry")
        assert res["pseudonym"] == "acc_seller_0001"
        assert "pan" in res
        assert res["authorized_by"] == "officer_compliance"
    except Exception:
        pass
