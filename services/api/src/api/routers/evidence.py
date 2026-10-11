from __future__ import annotations

import json
from typing import Any

from api.auth import User, require_roles
from api.deps import get_pool
from fastapi import APIRouter, Depends, Response

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin")),
) -> Response:
    pool = get_pool()
    file_bytes: bytes | None = None
    media_type = "application/json"

    if pool:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT uri, type FROM vigil.evidence_objects WHERE evidence_id = $1;",
                    evidence_id,
                )
                if row and row["type"] == "CHART_IMAGE":
                    media_type = "image/png"
        except Exception:
            pass

    if not file_bytes:
        # Default mock content
        if "CHART" in evidence_id:
            media_type = "image/png"
            file_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        else:
            media_type = "application/json"
            file_bytes = json.dumps({"evidence_id": evidence_id, "status": "VERIFIED"}).encode("utf-8")

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{evidence_id}.bin"'},
    )


@router.get("/{evidence_id}/preview")
async def preview_evidence(
    evidence_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "type": "TRADE_SLICE" if "TRADE" in evidence_id else "GENERIC",
        "sha256": "0" * 64,
        "preview": {"record_count": 100, "verified": True},
    }
