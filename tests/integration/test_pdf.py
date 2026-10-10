from __future__ import annotations

import io
import zipfile

import pypdf
import pytest
from evidence_engine.builder import EvidenceEngine


@pytest.mark.asyncio
async def test_pdf_dossier_sections_qr_and_manifest_hash() -> None:
    # AC-DOS-05: PDF has >= 6 sections, manifest hash, QR code, opens cleanly
    engine = EvidenceEngine()
    case_id = "case_pdf_test_01"
    symbol = "ZENITHSME"

    dossier, bundle_bytes = await engine.compile_dossier(case_id=case_id, symbol=symbol)

    with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as zf:
        assert "dossier.pdf" in zf.namelist()
        pdf_bytes = zf.read("dossier.pdf")

    # 1. Opens cleanly
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1

    # 2. Extract text and verify >= 6 sections
    text = "\n".join([page.extract_text() for page in reader.pages])

    required_sections = [
        "1. Executive Summary",
        "2. Subject Instrument",
        "3. Quantitative Market",
        "4. Social Intelligence",
        "5. Cyber-Forensics",
        "6. Regulatory Violations",
        "7. Cryptographic Certificate",
    ]

    for sec in required_sections:
        assert sec in text, f"Section '{sec}' missing in PDF text"

    # 3. Check manifest hash is present in PDF text
    digest_sha = dossier["signature"]["digest_sha256"]
    assert digest_sha in text, "Manifest digest SHA-256 missing in PDF text"
