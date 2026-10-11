from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from typing import Any

from vigil_common.hashing import sha256_hex
from vigil_common.ledger import append_entry
from vigil_common.logging import get_logger

logger = get_logger("reveal")


class IdentityRevealService:
    def __init__(self, pool: Any) -> None:
        self.pool = pool
        self.pepper = os.getenv("PSEUDONYM_PEPPER", "change-me-dev-pepper-32bytes-min").encode("utf-8")

    async def reveal_account(
        self,
        case_id: str,
        account_id: str,
        officer_id: str,
        justification: str,
        role: str = "compliance_officer",
    ) -> dict[str, Any]:
        """
        Compliance Identity Reveal Flow:
        Verifies case existence, account involvement, and reveals synthetic unmasking or returns NO_IDENTITY_MAPPING.
        Atomically appends to evidence_ledger and audit_log inside a single transaction.
        """
        path = f"/api/v1/accounts/{account_id}/reveal"
        method = "POST"

        # Validate justification
        if not justification or len(justification.strip()) < 10:
            if hasattr(self.pool, "acquire"):
                await self._record_audit(
                    officer_id, role, method, path, 400,
                    meta={"reason": "insufficient_justification", "account_id": account_id, "case_id": case_id},
                )
            raise ValueError("Justification required (minimum 10 characters) for identity reveal")

        # Validate case UUID
        try:
            cid = uuid.UUID(case_id)
        except (ValueError, AttributeError):
            if hasattr(self.pool, "acquire"):
                await self._record_audit(
                    officer_id, role, method, path, 400,
                    meta={"reason": "invalid_case_uuid", "account_id": account_id, "case_id": case_id},
                )
            raise ValueError(f"case_id '{case_id}' is not a valid UUID")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # 1. Verify case exists
                case_row = await conn.fetchrow(
                    """
                    SELECT case_id, symbol, window_start, window_end, is_synthetic
                    FROM vigil.cases
                    WHERE case_id = $1;
                    """,
                    cid,
                )
                if not case_row:
                    await conn.execute(
                        """
                        INSERT INTO vigil.audit_log (ts, user_id, role, method, path, status, request_hash, meta)
                        VALUES (now(), $1, $2, $3, $4, 404, $5, $6::jsonb);
                        """,
                        officer_id, role, method, path, "0" * 64,
                        json.dumps({"reason": "case_not_found", "case_id": case_id, "account_id": account_id}),
                    )
                    raise KeyError(f"Case {case_id} not found")

                symbol = case_row["symbol"]
                w_start = case_row["window_start"]
                w_end = case_row["window_end"]

                # 2. Verify account appears in that case (trades or orders)
                trade_row = await conn.fetchrow(
                    """
                    SELECT is_synthetic FROM vigil.trades
                    WHERE symbol = $1
                      AND (buyer_account = $2 OR seller_account = $2)
                      AND ts >= $3 AND ts <= $4
                    LIMIT 1;
                    """,
                    symbol, account_id, w_start, w_end,
                )

                if not trade_row:
                    # Also check orders_l3
                    order_row = await conn.fetchrow(
                        """
                        SELECT is_synthetic FROM vigil.orders_l3
                        WHERE symbol = $1 AND account_id = $2
                          AND ts >= $3 AND ts <= $4
                        LIMIT 1;
                        """,
                        symbol, account_id, w_start, w_end,
                    )
                    is_present = order_row is not None
                    is_synth = order_row["is_synthetic"] if order_row else False
                else:
                    is_present = True
                    is_synth = bool(trade_row["is_synthetic"])

                if not is_present:
                    await conn.execute(
                        """
                        INSERT INTO vigil.audit_log (ts, user_id, role, method, path, status, request_hash, meta)
                        VALUES (now(), $1, $2, $3, $4, 404, $5, $6::jsonb);
                        """,
                        officer_id, role, method, path, "0" * 64,
                        json.dumps({"reason": "account_not_in_case", "case_id": case_id, "account_id": account_id}),
                    )
                    raise KeyError(f"Account {account_id} does not appear in case {case_id}")

                # 3. Handle identity mapping
                if is_synth or case_row["is_synthetic"] or account_id.startswith("acc_"):
                    hmac_hex = hmac.new(self.pepper, account_id.encode("utf-8"), hashlib.sha256).hexdigest()[:8]
                    identity_payload = {
                        "identity_type": "SYNTHETIC",
                        "label": f"SYNTHETIC-ENTITY-{hmac_hex}",
                        "note": "synthetic scenario account, no real identity",
                        "account_id": account_id,
                        "case_id": str(cid),
                        "authorized_by": officer_id,
                        "justification": justification,
                    }
                else:
                    # Real / non-synthetic account with no external KYC mapping configured
                    await conn.execute(
                        """
                        INSERT INTO vigil.audit_log (ts, user_id, role, method, path, status, request_hash, meta)
                        VALUES (now(), $1, $2, $3, $4, 404, $5, $6::jsonb);
                        """,
                        officer_id, role, method, path, "0" * 64,
                        json.dumps({"reason": "no_identity_mapping", "case_id": case_id, "account_id": account_id}),
                    )
                    raise LookupError("NO_IDENTITY_MAPPING")

                # 4. Atomic Ledger and Audit Recording
                subject_sha = sha256_hex(f"{case_id}|{account_id}|{identity_payload['label']}".encode("utf-8"))
                await append_entry(
                    conn=conn,
                    case_id=cid,
                    entry_type="IDENTITY_REVEAL",
                    actor=officer_id,
                    subject_sha256=subject_sha,
                    payload={"account_id": account_id, "label": identity_payload["label"], "justification": justification},
                )

                await conn.execute(
                    """
                    INSERT INTO vigil.audit_log (ts, user_id, role, method, path, status, request_hash, meta)
                    VALUES (now(), $1, $2, $3, $4, 200, $5, $6::jsonb);
                    """,
                    officer_id, role, method, path, subject_sha,
                    json.dumps({
                        "case_id": str(cid),
                        "account_id": account_id,
                        "label": identity_payload["label"],
                        "justification": justification,
                    }),
                )

                return identity_payload

    async def _record_audit(
        self,
        user_id: str,
        role: str,
        method: str,
        path: str,
        status: int,
        meta: dict[str, Any],
    ) -> None:
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO vigil.audit_log (ts, user_id, role, method, path, status, request_hash, meta)
                    VALUES (now(), $1, $2, $3, $4, $5, $6, $7::jsonb);
                    """,
                    user_id, role, method, path, status, "0" * 64, json.dumps(meta),
                )
        except Exception as exc:
            logger.error("Failed to record denial audit log", error=str(exc))
