from __future__ import annotations

import pytest
from evidence_engine.builder import EvidenceEngine
from orchestrator.narrator import LLMNarrator


@pytest.mark.asyncio
async def test_llm_blocked_fallback_produces_template_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # AC-ORC-03: LLM blocked => dossier produced with narrative_mode="TEMPLATE"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")

    narrator = LLMNarrator(api_key=None)
    text, mode = narrator.generate_narrative(
        symbol="ZENITHSME",
        market_data={"suspect_volume": 1000},
        social_data={"hype_peak": 80.0},
        attribution_data={"rings": [{"accounts": ["acc_01", "acc_02"]}]},
        alignment_data={"best_lag_s": 120.0, "xcorr_peak": 0.65},
        evidence_ids={"TRADE_SLICE": "EV-TRADE_SLICE-1", "SOCIAL_SLICE": "EV-SOCIAL_SLICE-1", "GRAPH_EXPORT": "EV-GRAPH_EXPORT-1", "ANOMALY_EVENT": "EV-ANOMALY_EVENT-1"},
    )

    assert mode == "TEMPLATE"
    assert "ZENITHSME" in text
    assert "[EV-TRADE_SLICE-1]" in text

    # Compile via EvidenceEngine in template mode
    engine = EvidenceEngine()
    dossier, _ = await engine.compile_dossier(
        case_id="case_template_test_01",
        symbol="ZENITHSME",
        narrative_mode="TEMPLATE",
    )
    assert dossier.get("schema_version") == "1.0.0"
