from __future__ import annotations

import datetime
from typing import Any

import asyncpg
from vigil_common.hashing import sha256_hex
from vigil_common.ledger import GENESIS_PREV_HASH, compute_entry_hash


class IdentityRevealService:
    def __init__(self, pg_dsn: str) -> None:
        self.pg_dsn = pg_dsn

    async def reveal_account(
        self,
        case_id: str,
        pseudo_id: str,
        officer_id: str,
        justification: str,
    ) -> dict[str, Any]:
        """
        G-3 Compliance Identity Reveal Flow:
        Re-identifies HMAC-pseudonymized account with mandatory audit log & ledger recording.
        """
        if not justification or len(justification.strip()) < 10:
            raise ValueError("Justification required (minimum 10 characters) for identity reveal")

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.isoformat()

        # Deterministic synthetic/pepper unmasking:
        # In synthetic/demo environment, pseudonym acc_seller_... is mapped to simulated KYC entity
        raw_identity = {
            "pseudonym": pseudo_id,
            "pan": f"ABCDE{abs(hash(pseudo_id)) % 9000 + 1000}F",
            "name": f"Entity {pseudo_id[-6:]}",
            "broker_code": f"BRK-{abs(hash(pseudo_id)) % 500 + 100}",
            "revealed_at": now_iso,
            "authorized_by": officer_id,
            "justification": justification,
        }

        subject_sha = sha256_hex(f"{case_id}|{pseudo_id}|{raw_identity['pan']}".encode("utf-8"))

        conn = await asyncpg.connect(self.pg_dsn)
        try:
            # 1. Record Audit Log entry
            await conn.execute(
                """
                INSERT INTO vigil.audit_log (
                    user_id, role, action, target_type, target_id, details
                ) VALUES ($1, 'compliance_officer', 'IDENTITY_REVEAL', 'ACCOUNT', $2, $3::jsonb);
                """,
                officer_id,
                pseudo_id,
                f'{{"case_id": "{case_id}", "justification": "{justification}", "subject_sha256": "{subject_sha}"}}',
            )

            # 2. Append immutable record to evidence_ledger
            row = await conn.fetchrow(
                "SELECT entry_hash FROM vigil.evidence_ledger ORDER BY entry_id DESC LIMIT 1;"
            )
            prev_hash = row["entry_hash"] if row else GENESIS_PREV_HASH

            entry_hash = compute_entry_hash(
                prev_entry_hash=prev_hash,
                subject_sha256=subject_sha,
                ts=now_dt,
                entry_type="IDENTITY_REVEAL",
                actor=officer_id,
            )

            await conn.execute(
                """
                INSERT INTO vigil.evidence_ledger (
                    ts, case_id, entry_type, actor, subject_sha256, payload, prev_entry_hash, entry_hash
                ) VALUES ($1, $2::uuid, 'IDENTITY_REVEAL', $3, $4, $5::jsonb, $6, $7);
                """,
                now_dt,
                case_id,
                officer_id,
                subject_sha,
                f'{{"pseudo_id": "{pseudo_id}", "pan_hash": "{sha256_hex(raw_identity["pan"].encode("utf-8"))}"}}',
                prev_hash,
                entry_hash,
            )
        finally:
            await conn.close()

        return raw_identity
