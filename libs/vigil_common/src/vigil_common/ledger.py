from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from typing import Any

GENESIS_PREV_HASH = "0" * 64
LEDGER_ADVISORY_LOCK_ID = 849302194


def compute_entry_hash(
    prev_entry_hash: str,
    subject_sha256: str,
    ts: datetime.datetime,
    entry_type: str,
    actor: str,
) -> str:
    """
    Compute evidence_ledger entry_hash per ARCHITECTURE.md §3.3:
    hex(SHA256( prev_entry_hash || '|' || subject_sha256 || '|' || to_char(ts at utc,'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') || '|' || entry_type || '|' || actor ))
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    else:
        ts = ts.astimezone(datetime.timezone.utc)

    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = f"{prev_entry_hash}|{subject_sha256}|{ts_str}|{entry_type}|{actor}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def append_entry(
    conn: Any,
    case_id: str | uuid.UUID | None,
    entry_type: str,
    actor: str,
    subject_sha256: str,
    payload: dict[str, Any] | None = None,
    ts: datetime.datetime | None = None,
) -> dict[str, Any]:
    """
    Append an immutable entry to vigil.evidence_ledger inside an active transaction.
    Takes pg_advisory_xact_lock to serialize concurrent appends and guarantee a linear, non-forking chain.
    """
    await conn.execute("SELECT pg_advisory_xact_lock($1);", LEDGER_ADVISORY_LOCK_ID)

    if ts is None:
        ts = datetime.datetime.now(datetime.timezone.utc)
    elif ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    else:
        ts = ts.astimezone(datetime.timezone.utc)

    row = await conn.fetchrow(
        "SELECT entry_hash FROM vigil.evidence_ledger ORDER BY entry_id DESC LIMIT 1;"
    )
    prev_hash = row["entry_hash"] if row else GENESIS_PREV_HASH

    entry_hash = compute_entry_hash(
        prev_entry_hash=prev_hash,
        subject_sha256=subject_sha256,
        ts=ts,
        entry_type=entry_type,
        actor=actor,
    )

    payload_json = json.dumps(payload or {})
    case_uuid = uuid.UUID(str(case_id)) if case_id else None

    inserted = await conn.fetchrow(
        """
        INSERT INTO vigil.evidence_ledger (
            ts, case_id, entry_type, actor, subject_sha256, payload, prev_entry_hash, entry_hash
        ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
        RETURNING entry_id, ts, case_id, entry_type, actor, subject_sha256, payload, prev_entry_hash, entry_hash;
        """,
        ts,
        case_uuid,
        entry_type,
        actor,
        subject_sha256,
        payload_json,
        prev_hash,
        entry_hash,
    )
    return dict(inserted)


def verify_ledger_chain(entries: list[dict[str, Any]]) -> bool:
    """Verify that a sequence of ledger entries forms an unbroken cryptographic hash chain."""
    if not entries:
        return True

    for i, entry in enumerate(entries):
        if i == 0:
            expected_prev = entry.get("prev_entry_hash", GENESIS_PREV_HASH)
        else:
            expected_prev = entries[i - 1]["entry_hash"]

        if entry.get("prev_entry_hash") != expected_prev:
            return False

        ts = entry["ts"]
        if isinstance(ts, str):
            ts = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))

        calc_hash = compute_entry_hash(
            prev_entry_hash=entry["prev_entry_hash"],
            subject_sha256=entry["subject_sha256"],
            ts=ts,
            entry_type=entry["entry_type"],
            actor=entry["actor"],
        )
        if calc_hash != entry["entry_hash"]:
            return False

    return True
