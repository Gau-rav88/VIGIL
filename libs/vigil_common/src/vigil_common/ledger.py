import hashlib
from datetime import datetime, timezone
from typing import Any

GENESIS_PREV_HASH = "0" * 64


def compute_entry_hash(
    prev_entry_hash: str,
    subject_sha256: str,
    ts: datetime,
    entry_type: str,
    actor: str,
) -> str:
    """
    Compute evidence_ledger entry_hash per ARCHITECTURE.md §3.3:
    hex(SHA256( prev_entry_hash || '|' || subject_sha256 || '|' || to_char(ts at utc,'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') || '|' || entry_type || '|' || actor ))
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)

    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = f"{prev_entry_hash}|{subject_sha256}|{ts_str}|{entry_type}|{actor}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

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
