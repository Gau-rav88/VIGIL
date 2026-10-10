from __future__ import annotations

import os

import asyncpg
import pytest


@pytest.mark.asyncio
async def test_evidence_ledger_immutability_triggers() -> None:
    # AC-DOS-03: SQL UPDATE/DELETE on evidence_ledger raises
    dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@localhost:5434/vigil")
    conn = await asyncpg.connect(dsn)

    try:
        # Ensure at least 1 record exists
        row = await conn.fetchrow("SELECT entry_id FROM vigil.evidence_ledger LIMIT 1;")
        if not row:
            pytest.skip("No ledger rows to test mutation on")

        entry_id = row["entry_id"]

        # 1. Attempt UPDATE -> must raise exception
        with pytest.raises(asyncpg.PostgresError) as exc_info_update:
            await conn.execute(
                "UPDATE vigil.evidence_ledger SET actor = 'malicious_actor' WHERE entry_id = $1;",
                entry_id,
            )
        assert "append-only" in str(exc_info_update.value).lower()

        # 2. Attempt DELETE -> must raise exception
        with pytest.raises(asyncpg.PostgresError) as exc_info_delete:
            await conn.execute(
                "DELETE FROM vigil.evidence_ledger WHERE entry_id = $1;",
                entry_id,
            )
        assert "append-only" in str(exc_info_delete.value).lower()

    finally:
        await conn.close()
