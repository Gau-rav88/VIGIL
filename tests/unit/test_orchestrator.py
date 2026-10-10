from __future__ import annotations

import uuid

import pytest
from orchestrator.bus import AgentToolBus
from orchestrator.models import AgentMessage, WindowParams
from orchestrator.narrator import TemplateNarrator
from orchestrator.routes import (
    after_align,
    after_assess,
    after_enrich,
    after_open,
    after_review,
    after_sign,
    after_validate,
)
from orchestrator.validator import DossierValidator


def test_orchestrator_models() -> None:
    wp = WindowParams(start="2026-03-14T00:00:00Z", end="2026-03-14T02:00:00Z", widen_count=1)
    assert wp.widen_count == 1

    msg = AgentMessage(
        message_id="msg_1",
        correlation_id="corr_1",
        sender="orchestrator",
        recipient="quant_telemetry",
        command="REQUEST_MARKET_SLICE",
    )
    assert msg.version == "1.0.0"
    assert msg.sender == "orchestrator"


def test_routes_logic() -> None:
    # after_open
    assert after_open({"flags": ["MERGED"]}) == "merged"
    assert after_open({"flags": []}) == "enrich"

    # after_enrich
    assert after_enrich({"flags": ["MISSING_MARKET_SLICE", "MISSING_SOCIAL_SLICE"]}) == "failed"
    assert after_enrich({"flags": ["MISSING_MARKET_SLICE"]}) == "align"

    # after_align
    assert after_align({"alignment": {"p_value": 0.005, "xcorr_peak": 0.7}}) == "attribute"
    assert after_align({"alignment": {"p_value": 0.05, "xcorr_peak": 0.3}}) == "watchlist"

    # after_assess
    assert after_assess({"confidence": {"overall": 0.50}, "window": {"widen_count": 0}}) == "attribute"
    assert after_assess({"confidence": {"overall": 0.30}, "window": {"widen_count": 2}}) == "close"
    assert after_assess({"confidence": {"overall": 0.85}, "window": {"widen_count": 0}}) == "draft"

    # after_validate
    assert after_validate({"errors": []}) == "sign"
    assert after_validate({"errors": ["err"], "attempts": {"validate": 1}}) == "draft"
    assert after_validate({"errors": ["err"], "attempts": {"validate": 3}}) == "sign"

    # after_sign
    assert after_sign({"dossier_id": "dossier_1"}) == "await_review"
    assert after_sign({"dossier_id": None}) == "failed"

    # after_review
    assert after_review({"review": {"status": "APPROVED"}}) == "publish"
    assert after_review({"review": {"status": "REJECTED"}}) == "rejected"
    assert after_review({"review": {"status": "REWORK"}, "directives": [{"type": "FORCE_REATTRIBUTION"}]}) == "rework_attr"
    assert after_review({"review": {"status": "REWORK"}, "directives": []}) == "rework_draft"


def test_template_narrator() -> None:
    narrator = TemplateNarrator()
    ev_ids = {
        "TRADE_SLICE": "EV-TRADE_SLICE-123",
        "SOCIAL_SLICE": "EV-SOCIAL_SLICE-456",
        "GRAPH_EXPORT": "EV-GRAPH_EXPORT-789",
        "ANOMALY_EVENT": "EV-ANOMALY_EVENT-abc",
    }
    text, mode = narrator.generate_narrative("ZENITHSME", {}, {}, {}, {}, ev_ids)
    assert mode == "TEMPLATE"
    assert "ZENITHSME" in text
    assert "[EV-TRADE_SLICE-123]" in text
    assert "[EV-SOCIAL_SLICE-456]" in text


def test_dossier_validator_citation_check() -> None:
    valid_dossier_dict = {
        "schema_version": "1.0.0",
        "dossier_id": str(uuid.uuid4()),
        "version": 1,
        "case_id": "case_1",
        "generated_at": "2026-03-14T00:00:00Z",
        "jurisdiction": "SEBI_IN",
        "subject": {
            "symbol": "ZENITHSME",
            "exchange": "SYNTH",
            "window_start": "2026-03-14T00:00:00Z",
            "window_end": "2026-03-14T02:00:00Z",
            "manipulation_types": ["PUMP_AND_DUMP"],
        },
        "executive_summary": {
            "text": "Coordinated manipulation occurred [EV-TRADE_SLICE-1]. Social pump preceded trades [EV-SOCIAL_SLICE-1].",
            "citations": ["EV-TRADE_SLICE-1", "EV-SOCIAL_SLICE-1"],
        },
        "timeline": [
            {
                "ts": "2026-03-14T00:00:00Z",
                "track": "MARKET",
                "description": "Orders placed synchronously [EV-TRADE_SLICE-1].",
                "evidence_ids": ["EV-TRADE_SLICE-1"],
            }
        ],
        "market_evidence": {
            "total_volume": 1000,
            "suspect_volume": 800,
            "suspect_volume_ratio": 0.8,
            "price_move_pct": 20.0,
            "anomalies": ["ANOM-1"],
        },
        "social_evidence": {
            "channels": ["Telegram"],
            "message_count": 100,
            "hype_peak": 80.0,
            "cta_breakdown": {"BUY": 80},
            "near_duplicate_campaigns": 1,
        },
        "attribution": {
            "rings": [
                {
                    "ring_id": "r1",
                    "entity_id": "e1",
                    "ring_score": 0.9,
                    "accounts": ["acc_1", "acc_2"],
                    "methods": ["SHARED_DEVICE"],
                    "cycle_count": 2,
                    "net_volume": 800,
                    "evidence_ids": ["EV-TRADE_SLICE-1"],
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
                "rationale": "Circular trading",
                "legal_review_required": True,
            }
        ],
        "confidence": {
            "overall": 0.9,
            "completeness": 0.9,
            "components": {"mkt": 0.9},
        },
        "limitations": ["Simulated environment"],
        "evidence_manifest": [
            {
                "evidence_id": "EV-TRADE_SLICE-1",
                "type": "TRADE_SLICE",
                "sha256": "0" * 64,
                "uri": "evidence/EV-TRADE_SLICE-1.json",
                "bytes": 100,
                "captured_at": "2026-03-14T00:00:00Z",
            },
            {
                "evidence_id": "EV-SOCIAL_SLICE-1",
                "type": "SOCIAL_SLICE",
                "sha256": "0" * 64,
                "uri": "evidence/EV-SOCIAL_SLICE-1.json",
                "bytes": 100,
                "captured_at": "2026-03-14T00:00:00Z",
            },
        ],
        "merkle_root": "0" * 64,
        "ledger_anchor": {
            "entry_id": 1,
            "entry_hash": "0" * 64,
            "prev_entry_hash": "0" * 64,
        },
        "signature": {
            "alg": "Ed25519",
            "key_id": "dev-1",
            "canonicalization": "RFC8785-JCS",
            "digest_sha256": "0" * 64,
            "value_b64": "AA==",
            "signed_at": "2026-03-14T00:00:00Z",
        },
        "human_review": {
            "status": "NOT_REVIEWED",
        },
    }

    is_valid, errors = DossierValidator.validate(valid_dossier_dict)
    assert is_valid is True, f"Errors: {errors}"

    # Test validator failure branches
    invalid_dict = dict(valid_dossier_dict)
    invalid_dict["market_evidence"] = {
        "total_volume": 100,
        "suspect_volume": 200,  # exceeds total volume
        "suspect_volume_ratio": 0.5,
        "price_move_pct": 10.0,
        "anomalies": ["A1"],
    }
    is_valid_inv, errors_inv = DossierValidator.validate(invalid_dict)
    assert is_valid_inv is False
    assert any("exceeds" in e for e in errors_inv)

    # Test uncited sentence
    invalid_summary_dict = dict(valid_dossier_dict)
    invalid_summary_dict["executive_summary"] = {
        "text": "This sentence has no citation. Another sentence [EV-TRADE_SLICE-1].",
        "citations": ["EV-TRADE_SLICE-1"],
    }
    is_valid_sum, errors_sum = DossierValidator.validate(invalid_summary_dict)
    assert is_valid_sum is False
    assert any("lacks evidence citation" in e for e in errors_sum)


@pytest.mark.asyncio
async def test_tool_bus_fallback() -> None:
    bus = AgentToolBus("redis://localhost:9999/0")  # unreachable URL
    await bus.connect()
    res = await bus.send_command("quant_telemetry", "TEST_CMD", {"k": "v"})
    assert res["status"] == "SUCCESS"
    assert res["data"] == {"k": "v"}
    await bus.close()


@pytest.mark.asyncio
async def test_case_orchestrator_methods() -> None:
    from orchestrator.main import CaseOrchestrator
    orc = CaseOrchestrator()
    assert orc.running is False
    # Test _get_active_case_for_symbol when pool is None
    active = await orc._get_active_case_for_symbol("TEST")
    assert active is None

    # Test resume_case raises RuntimeError when graph is None
    with pytest.raises(RuntimeError):
        await orc.resume_case("case_1", {"status": "APPROVED"})

