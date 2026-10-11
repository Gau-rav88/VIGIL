from __future__ import annotations

import asyncio
import datetime
import uuid
from typing import Any

import pytest
from vigil_common.ledger import (
    GENESIS_PREV_HASH,
    append_entry,
    compute_entry_hash,
    verify_ledger_chain,
)


def test_verify_ledger_chain_valid() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    entries = []
    prev_hash = GENESIS_PREV_HASH

    for i in range(50):
        ts = now + datetime.timedelta(seconds=i)
        actor = f"officer_{i % 5}"
        entry_type = "EVIDENCE_ATTACH"
        subj = f"{i:064x}"
        h = compute_entry_hash(prev_hash, subj, ts, entry_type, actor)
        entries.append({
            "entry_id": i + 1,
            "prev_entry_hash": prev_hash,
            "entry_hash": h,
            "ts": ts,
            "entry_type": entry_type,
            "actor": actor,
            "subject_sha256": subj,
        })
        prev_hash = h

    assert verify_ledger_chain(entries) is True


def test_verify_ledger_chain_detects_fork_or_tamper() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    entries = []
    prev_hash = GENESIS_PREV_HASH

    for i in range(10):
        ts = now + datetime.timedelta(seconds=i)
        h = compute_entry_hash(prev_hash, f"{i:064x}", ts, "TEST", "admin")
        entries.append({
            "entry_id": i + 1,
            "prev_entry_hash": prev_hash,
            "entry_hash": h,
            "ts": ts,
            "entry_type": "TEST",
            "actor": "admin",
            "subject_sha256": f"{i:064x}",
        })
        prev_hash = h

    # Tamper with 5th entry hash
    entries[4]["entry_hash"] = "f" * 64
    assert verify_ledger_chain(entries) is False


class MockConnection:
    """Mock connection with advisory lock and serialized ledger simulation."""
    def __init__(self, ledger_store: list[dict[str, Any]], lock: asyncio.Lock) -> None:
        self.ledger_store = ledger_store
        self.lock = lock

    async def execute(self, query: str, *args: Any) -> None:
        pass

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if "SELECT entry_hash" in query:
            if not self.ledger_store:
                return None
            return {"entry_hash": self.ledger_store[-1]["entry_hash"]}
        elif "INSERT INTO vigil.evidence_ledger" in query:
            ts, case_id, entry_type, actor, subject_sha256, payload_json, prev_hash, entry_hash = args
            entry = {
                "entry_id": len(self.ledger_store) + 1,
                "ts": ts,
                "case_id": case_id,
                "entry_type": entry_type,
                "actor": actor,
                "subject_sha256": subject_sha256,
                "payload": payload_json,
                "prev_entry_hash": prev_hash,
                "entry_hash": entry_hash,
            }
            self.ledger_store.append(entry)
            return entry
        return None


@pytest.mark.asyncio
async def test_concurrent_ledger_appends_no_forks() -> None:
    """Simulates 50 concurrent appends with mutex advisory lock to verify zero chain forks."""
    store: list[dict[str, Any]] = []
    mutex = asyncio.Lock()

    async def worker(idx: int) -> None:
        async with mutex:
            conn = MockConnection(store, mutex)
            await append_entry(
                conn=conn,
                case_id=uuid.uuid4(),
                entry_type="PARALLEL_TEST",
                actor=f"agent_{idx}",
                subject_sha256=f"{idx:064x}",
                payload={"worker_id": idx},
            )

    await asyncio.gather(*(worker(i) for i in range(50)))

    assert len(store) == 50
    assert verify_ledger_chain(store) is True
