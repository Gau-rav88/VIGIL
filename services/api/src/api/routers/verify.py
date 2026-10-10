from __future__ import annotations

import os
import tempfile
from typing import Any

from fastapi import APIRouter, File, Request, UploadFile
from vigil_common.verifier import verify_bundle

router = APIRouter(prefix="/api/v1", tags=["verify"])


@router.post("/verify")
async def verify_bundle_upload(
    request: Request,
    file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    # Support both multipart form file upload and raw binary body
    if file:
        contents = await file.read()
    else:
        contents = await request.body()

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = dict(verify_bundle(tmp_path))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return result


@router.post("/dossiers/verify-upload")
async def verify_upload_alias(request: Request) -> dict[str, Any]:
    return await verify_bundle_upload(request)
