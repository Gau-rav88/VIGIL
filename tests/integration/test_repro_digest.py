from __future__ import annotations

import pytest
from evidence_engine.builder import EvidenceEngine


@pytest.mark.asyncio
async def test_identical_inputs_yield_identical_digest_in_template_mode() -> None:
    # P6-G1: Same inputs + config hash => identical dossier digest (NFR-INT-02) when narrative_mode=TEMPLATE
    engine = EvidenceEngine()
    case_id = "case_repro_01"
    symbol = "ZENITHSME"
    fixed_ts = "2026-03-14T10:00:00+00:00"

    dossier_1, bundle_1 = await engine.compile_dossier(
        case_id=case_id,
        symbol=symbol,
        narrative_mode="TEMPLATE",
        captured_at=fixed_ts,
    )

    dossier_2, bundle_2 = await engine.compile_dossier(
        case_id=case_id,
        symbol=symbol,
        narrative_mode="TEMPLATE",
        captured_at=fixed_ts,
    )

    digest_1 = dossier_1["signature"]["digest_sha256"]
    digest_2 = dossier_2["signature"]["digest_sha256"]
    assert digest_1 == digest_2, "Digest must be 100% reproducible given identical inputs"

    merkle_1 = dossier_1["merkle_root"]
    merkle_2 = dossier_2["merkle_root"]
    assert merkle_1 == merkle_2, "Merkle root must be 100% reproducible"
