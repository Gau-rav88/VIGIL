from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from vigil_common.signing import FileEd25519Signer


def get_key_paths() -> tuple[Path, Path]:
    candidates = [
        (Path("/keys/dev_ed25519.pem"), Path("/keys/dev_ed25519.pub")),
        (Path("keys/dev_ed25519.pem"), Path("keys/dev_ed25519.pub")),
        (Path(__file__).resolve().parents[4] / "keys" / "dev_ed25519.pem", Path(__file__).resolve().parents[4] / "keys" / "dev_ed25519.pub"),
    ]
    for priv, pub in candidates:
        if priv.exists():
            return priv, pub
    return Path("keys/dev_ed25519.pem"), Path("keys/dev_ed25519.pub")


class EvidenceEngine:
    def __init__(self, pg_dsn: str | None = None) -> None:
        self.pg_dsn = pg_dsn or os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil")
        priv_path, pub_path = get_key_paths()
        self.signer = FileEd25519Signer(str(priv_path), key_id="dev-2026-01")
        self.public_key_pem = self.signer.public_key_pem()

    async def compile_dossier(
        self,
        case_id: str,
        symbol: str,
        attribution_rings: list[dict[str, Any]] | None = None,
        anomalies: list[dict[str, Any]] | None = None,
        human_review: dict[str, Any] | None = None,
        version: int = 1,
        narrative_mode: str = "TEMPLATE",
        custom_executive_summary: str | None = None,
        captured_at: str | None = None,
    ) -> tuple[dict[str, Any], bytes]:
        # Delegate to evidence_engine builder
        from evidence_engine.builder import EvidenceEngine as CoreEvidenceEngine
        core = CoreEvidenceEngine(self.pg_dsn)
        return await core.compile_dossier(
            case_id=case_id,
            symbol=symbol,
            attribution_rings=attribution_rings,
            anomalies=anomalies,
            human_review=human_review,
            version=version,
            narrative_mode=narrative_mode,
            custom_executive_summary=custom_executive_summary,
            captured_at=captured_at,
        )
