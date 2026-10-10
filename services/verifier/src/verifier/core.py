from __future__ import annotations

from pathlib import Path
from typing import Any

from vigil_common.verifier import verify_bundle as common_verify_bundle


def verify_bundle(bundle_path: str | Path, pubkey_pem: str | None = None) -> dict[str, Any]:
    return common_verify_bundle(bundle_path, pubkey_pem)
