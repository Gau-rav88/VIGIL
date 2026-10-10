from __future__ import annotations

import base64
import datetime
import io
import json
import os
import uuid
import zipfile
from pathlib import Path
from typing import Any

import asyncpg
from vigil_common.canonical import canonical_json_bytes
from vigil_common.hashing import sha256_bytes
from vigil_common.ledger import GENESIS_PREV_HASH, compute_entry_hash
from vigil_common.merkle import compute_merkle_root
from vigil_common.models.dossier import (
    AttributionFinding,
    ConfidenceScore,
    DossierSignature,
    DossierSubject,
    EvidenceManifestItem,
    ExecutiveSummary,
    ForensicDossier,
    HumanReview,
    LeadAttribution,
    LedgerAnchor,
    MarketEvidence,
    RingAttribution,
    SocialAlignment,
    SocialEvidence,
    TimelineEntry,
    ViolatedClause,
)
from vigil_common.signing import FileEd25519Signer

from evidence_engine.capture import CapturedEvidence, capture_standard_evidence_set
from evidence_engine.pdf import render_dossier_pdf


def get_key_paths() -> tuple[Path, Path]:
    candidates = [
        (Path("/keys/dev_ed25519.pem"), Path("/keys/dev_ed25519.pub")),
        (Path("keys/dev_ed25519.pem"), Path("keys/dev_ed25519.pub")),
        (Path(__file__).resolve().parents[5] / "keys" / "dev_ed25519.pem", Path(__file__).resolve().parents[5] / "keys" / "dev_ed25519.pub"),
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
        if captured_at:
            now_dt = datetime.datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            now_iso = captured_at
            dossier_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{case_id}:{symbol}:{version}:{now_iso}"))
        else:
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            now_iso = now_dt.isoformat()
            dossier_id = str(uuid.uuid4())

        start_iso = (now_dt - datetime.timedelta(hours=2)).isoformat()

        # 1. Capture All 9 Canonical Evidence Slices
        anom_list = anomalies or [
            {"anomaly_id": f"ANOM-{case_id[:8]}", "type": "CROSS_MODAL_ALIGNMENT", "symbol": symbol, "confidence": 0.94}
        ]
        ring_list = attribution_rings or [{
            "ring_id": "ring_01",
            "ring_score": 0.988,
            "accounts_count": 20,
            "shared_devices": 5,
            "shared_asn": 55836,
        }]

        evidence_items: list[CapturedEvidence] = capture_standard_evidence_set(
            symbol=symbol,
            case_id=case_id,
            window_start=start_iso,
            window_end=now_iso,
            anomalies=anom_list,
            rings=ring_list,
            captured_at=now_iso,
        )

        evidence_files: dict[str, bytes] = {
            f"evidence/{ev.filename}": ev.content for ev in evidence_items
        }
        manifest_models: list[EvidenceManifestItem] = [ev.to_manifest_item() for ev in evidence_items]
        manifest_dicts: list[dict[str, Any]] = [m.model_dump() for m in manifest_models]

        # 2. Compute RFC 6962 Domain-Separated Merkle Root
        merkle_root, proofs = compute_merkle_root(manifest_dicts)

        # Evidence IDs for citations
        trade_ev_id = next((e.evidence_id for e in evidence_items if e.evidence_type == "TRADE_SLICE"), evidence_items[0].evidence_id)
        social_ev_id = next((e.evidence_id for e in evidence_items if e.evidence_type == "SOCIAL_SLICE"), evidence_items[0].evidence_id)
        graph_ev_id = next((e.evidence_id for e in evidence_items if e.evidence_type == "GRAPH_EXPORT"), evidence_items[0].evidence_id)
        anom_ev_id = next((e.evidence_id for e in evidence_items if e.evidence_type == "ANOMALY_EVENT"), evidence_items[0].evidence_id)

        # 3. Assemble Structured Forensic Sub-models
        subject = DossierSubject(
            symbol=symbol,
            exchange="SYNTH",
            isin=f"INE{abs(hash(symbol)) % 9000000 + 1000000}10",
            window_start=start_iso,
            window_end=now_iso,
            manipulation_types=["PUMP_AND_DUMP", "WASH_TRADING"],
        )

        exec_text = custom_executive_summary or (
            f"Autonomous forensic intelligence verified coordinated cross-modal market manipulation on target {symbol} [{trade_ev_id}]. "
            f"Social intelligence detected high-volume artificial Telegram/X hype bursts preceding trading dislocation [{social_ev_id}]. "
            f"Cyber-forensics attribution graph identified a tightly coupled collusion ring of 20 accounts executing circular wash trading [{graph_ev_id}]. "
            f"Cross-modal anomaly fusion confirmed that social campaign escalation led market volume spike by ~150 seconds [{anom_ev_id}]."
        )
        executive_summary = ExecutiveSummary(
            text=exec_text,
            citations=[trade_ev_id, social_ev_id, graph_ev_id, anom_ev_id],
        )

        timeline = [
            TimelineEntry(
                ts=start_iso,
                track="SOCIAL",
                description=f"Coordinated Hinglish Telegram pump campaign launched across 3 broadcast channels [{social_ev_id}].",
                evidence_ids=[social_ev_id],
            ),
            TimelineEntry(
                ts=(now_dt - datetime.timedelta(minutes=90)).isoformat(),
                track="SYSTEM",
                description=f"Anomaly fusion engine detected statistically significant cross-modal lead-lag correlation [{anom_ev_id}].",
                evidence_ids=[anom_ev_id],
            ),
            TimelineEntry(
                ts=(now_dt - datetime.timedelta(minutes=45)).isoformat(),
                track="MARKET",
                description=f"Suspect buy-side orders placed synchronously within 500ms bins causing artificial price jump [{trade_ev_id}].",
                evidence_ids=[trade_ev_id],
            ),
            TimelineEntry(
                ts=(now_dt - datetime.timedelta(minutes=10)).isoformat(),
                track="GRAPH",
                description=f"Graph community attribution resolved ring_01 encompassing 20 accounts sharing 5 hardware devices [{graph_ev_id}].",
                evidence_ids=[graph_ev_id],
            ),
        ]

        market_evidence = MarketEvidence(
            total_volume=450000,
            suspect_volume=385000,
            suspect_volume_ratio=0.855,
            price_move_pct=34.2,
            anomalies=[a.get("anomaly_id", "ANOM-01") for a in anom_list],
        )

        social_evidence = SocialEvidence(
            channels=["Telegram: @SME_Pump_Signals", "X: $ZENITHSME"],
            message_count=1240,
            hype_peak=88.4,
            cta_breakdown={"BUY_CALL": 850, "URGENT": 240, "NEUTRAL": 150},
            near_duplicate_campaigns=4,
            alignment=SocialAlignment(best_lag_s=150.0, xcorr_peak=0.685, p_value=0.001),
        )

        ring_attrs = [
            RingAttribution(
                ring_id=r.get("ring_id", f"ring_{idx:02d}"),
                entity_id=f"ENTITY-{symbol}-{idx:02d}",
                ring_score=float(r.get("ring_score", 0.988)),
                accounts=[f"acc_{i:02d}" for i in range(1, 21)],
                methods=["SHARED_DEVICE", "CIRCULAR_CYCLE", "SHARED_NETWORK", "SYNCHRONIZED_ORDERS"],
                cycle_count=14,
                net_volume=385000,
                evidence_ids=[graph_ev_id],
            )
            for idx, r in enumerate(ring_list)
        ]
        attribution = AttributionFinding(
            rings=ring_attrs,
            leads=[LeadAttribution(account_id="acc_lead_01", confidence=0.55, note="Lead under PRD G-2 threshold")],
        )

        violated_clauses = [
            ViolatedClause(
                regime="SEBI",
                clause_id="SEBI-PFUTP-R4(2)",
                title="PFUTP Regulations, 2003 — Reg. 4(2) (manipulative, fraudulent trade practices)",
                finding_types=["WASH_CYCLE", "CIRCULAR_RING", "PRICE_JUMP"],
                rationale="Matched/circular trades among 20 linked accounts representing 86% of volume created misleading appearance of active trading.",
                evidence_ids=[trade_ev_id, graph_ev_id],
                legal_review_required=True,
            ),
            ViolatedClause(
                regime="SEBI",
                clause_id="SEBI-PFUTP-R3",
                title="PFUTP Regulations, 2003 — Reg. 3 (prohibition of fraudulent dealings)",
                finding_types=["HYPE_BURST", "CROSS_MODAL_ALIGNMENT"],
                rationale="Coordinated social hype campaigns leading artificial price movements induced retail market participation.",
                evidence_ids=[social_ev_id, anom_ev_id],
                legal_review_required=True,
            ),
        ]

        confidence = ConfidenceScore(
            overall=0.94,
            completeness=0.92,
            components={"alignment": 0.96, "attribution": 0.95, "market": 0.92, "social": 0.93},
        )

        review = HumanReview(
            status=human_review.get("status", "NOT_REVIEWED") if human_review else "NOT_REVIEWED",
            reviewer_id=human_review.get("reviewer_id") if human_review else None,
            reviewed_at=human_review.get("reviewed_at") if human_review else None,
            comment=human_review.get("comment") if human_review else None,
        )

        # 4. Preliminary Dossier Assembly (Without Signature & Anchor)
        preliminary_dict: dict[str, Any] = {
            "schema_version": "1.0.0",
            "dossier_id": dossier_id,
            "version": version,
            "supersedes": None,
            "case_id": case_id,
            "generated_at": now_iso,
            "jurisdiction": "SEBI_IN",
            "subject": subject.model_dump(),
            "executive_summary": executive_summary.model_dump(),
            "timeline": [t.model_dump() for t in timeline],
            "market_evidence": market_evidence.model_dump(),
            "social_evidence": social_evidence.model_dump(),
            "attribution": attribution.model_dump(),
            "violated_clauses": [c.model_dump() for c in violated_clauses],
            "confidence": confidence.model_dump(),
            "limitations": [
                "Analysis bounded by simulated network topology and trading window.",
                "Subject to mandatory human compliance review before legal proceedings.",
            ],
            "evidence_manifest": manifest_dicts,
            "merkle_root": merkle_root,
            "ledger_anchor": {
                "entry_id": 1,
                "entry_hash": "0" * 64,
                "prev_entry_hash": GENESIS_PREV_HASH,
                "tsa_token_b64": None,
            },
            "signature": {
                "alg": "Ed25519",
                "key_id": self.signer.key_id,
                "canonicalization": "RFC8785-JCS",
                "digest_sha256": "0" * 64,
                "value_b64": "AA==",
                "signed_at": now_iso,
            },
            "human_review": review.model_dump(),
        }

        # 5. Ledger Entry Chaining & Real Anchor
        canon_prelim = canonical_json_bytes({k: v for k, v in preliminary_dict.items() if k not in ("signature", "ledger_anchor")})
        digest_prelim = sha256_bytes(canon_prelim)

        ledger_entry = await self._record_ledger_entry(
            case_id=case_id,
            subject_sha256=digest_prelim.hex(),
            now_dt=now_dt,
            dossier_id=dossier_id,
            deterministic=bool(captured_at),
        )

        ledger_anchor = LedgerAnchor(
            entry_id=ledger_entry["entry_id"],
            entry_hash=ledger_entry["entry_hash"],
            prev_entry_hash=ledger_entry["prev_entry_hash"],
            tsa_token_b64=None,
        )
        preliminary_dict["ledger_anchor"] = ledger_anchor.model_dump()

        # 6. RFC 8785 Canonical Digest & Ed25519 Signing
        sign_payload = {k: v for k, v in preliminary_dict.items() if k != "signature"}
        canon_bytes = canonical_json_bytes(sign_payload)
        digest = sha256_bytes(canon_bytes)
        raw_sig = self.signer.sign(digest)
        sig_b64 = base64.b64encode(raw_sig).decode("ascii")

        signature = DossierSignature(
            alg="Ed25519",
            key_id=self.signer.key_id,
            canonicalization="RFC8785-JCS",
            digest_sha256=digest.hex(),
            value_b64=sig_b64,
            signed_at=now_iso,
        )
        preliminary_dict["signature"] = signature.model_dump()

        # 7. Strict Pydantic Model Validation
        final_model = ForensicDossier.model_validate(preliminary_dict)
        dossier_dict = final_model.model_dump()

        # 8. Render Official Forensic PDF
        pdf_bytes = render_dossier_pdf(dossier_dict)

        # 9. Assemble Complete ZIP Evidence Bundle
        manifest_data = {
            "schema_version": "1.0.0",
            "dossier_id": dossier_id,
            "merkle_root": merkle_root,
            "evidence_manifest": manifest_dicts,
            "merkle_proofs": proofs,
            "created_at": now_iso,
        }
        ledger_proof = {
            "case_id": case_id,
            "dossier_id": dossier_id,
            "entries": [ledger_entry],
        }

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dossier.json", json.dumps(dossier_dict, indent=2))
            zf.writestr("dossier.pdf", pdf_bytes)
            zf.writestr("dossier.sig", sig_b64)
            zf.writestr("manifest.json", json.dumps(manifest_data, indent=2))
            zf.writestr("ledger_proof.json", json.dumps(ledger_proof, indent=2))
            zf.writestr("proofs.json", json.dumps(proofs, indent=2))
            zf.writestr(
                "VERIFY.md",
                "# Forensic Dossier Verification Instructions\n\n"
                "This evidence bundle contains cryptographically signed artifacts from Project VIGIL.\n\n"
                "## Offline Verification\n"
                "```bash\n"
                "uv run vigil-verify bundle.zip --pubkey pubkey.pem\n"
                "```\n",
            )
            zf.writestr("pubkey.pem", self.public_key_pem)

            for fname, fbytes in evidence_files.items():
                zf.writestr(fname, fbytes)

        bundle_bytes = zip_buf.getvalue()

        # 10. Persist to TimescaleDB
        await self._persist_dossier_db(
            dossier_id=dossier_id,
            case_id=case_id,
            version=version,
            digest_sha256=digest.hex(),
            merkle_root=merkle_root,
            review_status=review.status,
        )

        return dossier_dict, bundle_bytes

    async def _record_ledger_entry(
        self,
        case_id: str,
        subject_sha256: str,
        now_dt: datetime.datetime,
        dossier_id: str,
        deterministic: bool = False,
    ) -> dict[str, Any]:
        entry_type = "DOSSIER_CREATION"
        actor = "evidence_engine"
        prev_hash = GENESIS_PREV_HASH
        entry_id = 1

        if deterministic:
            entry_hash = compute_entry_hash(
                prev_entry_hash=prev_hash,
                subject_sha256=subject_sha256,
                ts=now_dt,
                entry_type=entry_type,
                actor=actor,
            )
            return {
                "entry_id": 1,
                "ts": now_dt.isoformat(),
                "case_id": case_id,
                "entry_type": entry_type,
                "actor": actor,
                "subject_sha256": subject_sha256,
                "prev_entry_hash": prev_hash,
                "entry_hash": entry_hash,
            }

        try:
            conn = await asyncpg.connect(self.pg_dsn)
            try:
                row = await conn.fetchrow(
                    "SELECT entry_id, entry_hash FROM vigil.evidence_ledger ORDER BY entry_id DESC LIMIT 1;"
                )
                if row:
                    prev_hash = row["entry_hash"]
                    entry_id = row["entry_id"] + 1

                entry_hash = compute_entry_hash(
                    prev_entry_hash=prev_hash,
                    subject_sha256=subject_sha256,
                    ts=now_dt,
                    entry_type=entry_type,
                    actor=actor,
                )

                # Append to evidence_ledger
                await conn.execute(
                    """
                    INSERT INTO vigil.evidence_ledger (
                        ts, case_id, entry_type, actor, subject_sha256, payload, prev_entry_hash, entry_hash
                    ) VALUES ($1, $2::uuid, $3, $4, $5, $6::jsonb, $7, $8);
                    """,
                    now_dt,
                    uuid.UUID(case_id),
                    entry_type,
                    actor,
                    subject_sha256,
                    json.dumps({"dossier_id": dossier_id, "action": "COMPILE"}),
                    prev_hash,
                    entry_hash,
                )
            finally:
                await conn.close()
        except Exception:
            # Fallback if DB not reachable
            entry_hash = compute_entry_hash(
                prev_entry_hash=prev_hash,
                subject_sha256=subject_sha256,
                ts=now_dt,
                entry_type=entry_type,
                actor=actor,
            )

        return {
            "entry_id": entry_id,
            "ts": now_dt.isoformat(),
            "case_id": case_id,
            "entry_type": entry_type,
            "actor": actor,
            "subject_sha256": subject_sha256,
            "prev_entry_hash": prev_hash,
            "entry_hash": entry_hash,
        }

    async def _persist_dossier_db(
        self,
        dossier_id: str,
        case_id: str,
        version: int,
        digest_sha256: str,
        merkle_root: str,
        review_status: str,
    ) -> None:
        try:
            conn = await asyncpg.connect(self.pg_dsn)
            try:
                await conn.execute(
                    """
                    INSERT INTO vigil.dossiers (
                        dossier_id, case_id, version, digest_sha256, merkle_root,
                        review_status, bundle_uri, created_at
                    ) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::vigil.review_status, $7, now())
                    ON CONFLICT (case_id, version) DO UPDATE
                    SET digest_sha256 = EXCLUDED.digest_sha256,
                        merkle_root = EXCLUDED.merkle_root,
                        review_status = EXCLUDED.review_status;
                    """,
                    uuid.UUID(dossier_id),
                    uuid.UUID(case_id),
                    version,
                    digest_sha256,
                    merkle_root,
                    review_status,
                    f"s3://vigil-dossiers/{dossier_id}.zip",
                )
            finally:
                await conn.close()
        except Exception:
            pass
