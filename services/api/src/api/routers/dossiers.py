import io
import json
import os
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from api.auth import User, require_roles
from api.deps import bundle_cache, dossier_cache, get_pool
from api.errors import ProblemException
from fastapi import APIRouter, Depends, Response
from vigil_common.verifier import verify_bundle

try:
    from tests.fixtures.demo.fixtures import DEMO_BUNDLE_BYTES, is_demo_enabled
except ImportError:
    def is_demo_enabled() -> bool:
        return False
    DEMO_BUNDLE_BYTES = b""

router = APIRouter(prefix="/api/v1/dossiers", tags=["dossiers"])


async def ensure_dossier_bundle(dossier_id: str) -> tuple[dict[str, Any], bytes]:
    # 1. Check in-memory read cache
    dossier_data = dossier_cache.get(dossier_id)
    bundle_bytes = bundle_cache.get(dossier_id)
    if dossier_data and bundle_bytes:
        return dossier_data, bundle_bytes

    # 2. Check disk storage (reports/dossiers/{dossier_id}.zip)
    candidates = [
        Path(f"reports/dossiers/{dossier_id}.zip"),
        Path(f"/app/reports/dossiers/{dossier_id}.zip"),
        Path(f"reports/sample_bundle/{dossier_id}.zip"),
    ]
    for c in candidates:
        if c.exists():
            bundle_bytes = c.read_bytes()
            try:
                with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as z:
                    dossier_data = json.loads(z.read("dossier.json").decode("utf-8"))
                dossier_cache[dossier_id] = dossier_data
                bundle_cache[dossier_id] = bundle_bytes
                return dossier_data, bundle_bytes
            except Exception:
                pass

    # 3. Check database (vigil.dossiers)
    pool = get_pool()
    if pool:
        try:
            cid = uuid.UUID(dossier_id)
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT bundle_uri FROM vigil.dossiers WHERE dossier_id = $1;",
                    cid,
                )
                if row and row["bundle_uri"]:
                    b_path = Path(row["bundle_uri"])
                    if b_path.exists():
                        bundle_bytes = b_path.read_bytes()
                        with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as z:
                            dossier_data = json.loads(z.read("dossier.json").decode("utf-8"))
                        dossier_cache[dossier_id] = dossier_data
                        bundle_cache[dossier_id] = bundle_bytes
                        return dossier_data, bundle_bytes
        except Exception:
            pass

    if is_demo_enabled():
        return {"dossier_id": dossier_id, "data_source": "demo_fixture"}, DEMO_BUNDLE_BYTES

    # Unknown dossier -> 404
    raise ProblemException(
        status_code=404,
        title="Not Found",
        detail=f"Dossier {dossier_id} not found",
        type_uri="https://api.vigil.dev/errors/not-found",
    )


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
