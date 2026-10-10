from __future__ import annotations

import json
from pathlib import Path

import pytest
from evidence_engine.builder import EvidenceEngine
from orchestrator.validator import DossierValidator
from vigil_common.models.dossier import ForensicDossier


@pytest.mark.asyncio
async def test_dossier_validates_against_schema_and_cites_evidence() -> None:
    # AC-DOS-01: Dossier validates against forensic_dossier.schema.json; all claims cited
    engine = EvidenceEngine()
    case_id = "case_schema_test_01"
    symbol = "ZENITHSME"

    dossier_dict, bundle_bytes = await engine.compile_dossier(case_id=case_id, symbol=symbol)

    # 1. Pydantic Model Validation
    model = ForensicDossier.model_validate(dossier_dict)
    assert model.dossier_id == dossier_dict["dossier_id"]
    assert model.subject.symbol == symbol

    # 2. JSON Schema Validation against committed schema file
    schema_path = Path("libs/vigil_common/schemas/forensic_dossier.schema.json")
    if schema_path.exists():
        import jsonschema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=dossier_dict, schema=schema)

    # 3. Citation Check (every claim/sentence cited)
    is_valid, errors = DossierValidator.validate(dossier_dict)
    assert is_valid is True, f"Validation errors: {errors}"
    assert len(errors) == 0
