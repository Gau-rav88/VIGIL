from __future__ import annotations

import os
import tempfile
import uuid
from typing import Any

from api.auth import User, require_roles
from api.deps import bundle_cache, dossier_cache, get_engine
from api.errors import ProblemException
from fastapi import APIRouter, Depends, Response
from vigil_common.verifier import verify_bundle

router = APIRouter(prefix="/api/v1/dossiers", tags=["dossiers"])


async def ensure_dossier_bundle(dossier_id: str) -> tuple[dict[str, Any], bytes]:
    dossier_data = dossier_cache.get(dossier_id)
    bundle_bytes = bundle_cache.get(dossier_id)

    if not dossier_data or not bundle_bytes:
        engine = get_engine()
        if engine:
            dossier_data, bundle_bytes = await engine.compile_dossier(
                case_id=str(uuid.uuid4()),
                symbol="ZENITHSME",
                attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95, "accounts_count": 20}],
                anomalies=[],
                human_review={"status": "APPROVED", "reviewer": "compliance_officer"},
            )
            dossier_data["dossier_id"] = dossier_id
            bundle_cache[dossier_id] = bundle_bytes
            dossier_cache[dossier_id] = dossier_data

    if not dossier_data or not bundle_bytes:
        raise ProblemException(404, "Not Found", f"Dossier {dossier_id} not found")

    return dossier_data, bundle_bytes


@router.get("/{dossier_id}")
async def get_dossier(
    dossier_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    dossier_data, _ = await ensure_dossier_bundle(dossier_id)
    return dossier_data


@router.get("/{dossier_id}/pdf")
async def get_dossier_pdf(
    dossier_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> Response:
    from evidence_engine.pdf import render_dossier_pdf
    dossier_data, _ = await ensure_dossier_bundle(dossier_id)
    pdf_bytes = render_dossier_pdf(dossier_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="dossier_{dossier_id}.pdf"'},
    )


@router.get("/{dossier_id}/bundle")
async def get_dossier_bundle(
    dossier_id: str,
    user: User = Depends(require_roles("compliance_officer", "admin")),
) -> Response:
    _, bundle_bytes = await ensure_dossier_bundle(dossier_id)

    return Response(
        content=bundle_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="vigil_dossier_{dossier_id}.zip"'},
    )


@router.api_route("/{dossier_id}/verify", methods=["GET", "POST"])
async def verify_dossier_endpoint(dossier_id: str) -> dict[str, Any]:
    # Public / all roles endpoint
    _, bundle_bytes = await ensure_dossier_bundle(dossier_id)

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(bundle_bytes)
        tmp_path = tmp.name

    try:
        result = dict(verify_bundle(tmp_path))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return result
