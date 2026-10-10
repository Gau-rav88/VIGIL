from __future__ import annotations

import io
import tempfile
import zipfile

import pytest
from evidence_engine.builder import EvidenceEngine
from vigil_common.verifier import verify_bundle


@pytest.mark.asyncio
async def test_bundle_valid_and_tamper_fails_with_named_failure() -> None:
    # AC-DOS-02: POST /verify -> valid:true; flipping any single byte of any evidence file -> valid:false with named failure
    engine = EvidenceEngine()
    case_id = "case_tamper_test_01"
    symbol = "ZENITHSME"

    dossier, bundle_bytes = await engine.compile_dossier(case_id=case_id, symbol=symbol)

    # 1. Untampered bundle is valid
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(bundle_bytes)
        valid_path = f.name

    result_valid = verify_bundle(valid_path)
    assert result_valid["valid"] is True
    assert len(result_valid["failed"]) == 0

    # 2. Tamper with an evidence file inside the bundle
    in_buf = io.BytesIO(bundle_bytes)
    out_buf = io.BytesIO()
    tampered_evidence_id = ""

    with zipfile.ZipFile(in_buf, "r") as zin, zipfile.ZipFile(out_buf, "w") as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename.startswith("evidence/") and not tampered_evidence_id:
                # Corrupt one byte of this evidence file
                tampered_evidence_id = item.filename.replace("evidence/", "").split(".")[0]
                content = content + b"\x00_TAMPERED"
            zout.writestr(item, content)

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(out_buf.getvalue())
        tampered_path = f.name

    result_tampered = verify_bundle(tampered_path)
    assert result_tampered["valid"] is False
    assert any(f"HASH_MISMATCH_{tampered_evidence_id}" in err for err in result_tampered["failed"])
