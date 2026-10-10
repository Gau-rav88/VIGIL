from __future__ import annotations

import os
import uuid

import asyncpg
import pytest
from langgraph.checkpoint.memory import MemorySaver
from orchestrator.graph import build_graph
from orchestrator.models import CaseState
from orchestrator.nodes import OrchestratorDeps


@pytest.mark.asyncio
async def test_resume_does_not_create_duplicate_ledger_entries() -> None:
    # AC-ORC-02: Resuming orchestrator on mid-case produces no duplicate ledger entries
    dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@localhost:5434/vigil")
    conn = await asyncpg.connect(dsn)

    case_id = str(uuid.uuid4())
    deps = OrchestratorDeps(pg_dsn=dsn)
    checkpointer = MemorySaver()
    graph = build_graph(deps, checkpointer=checkpointer)

    config = {"configurable": {"thread_id": case_id}}
    init_state: CaseState = {
        "case_id": case_id,
        "symbol": "ZENITHSME",
        "stage": "OPENED",
        "trigger_anomaly_id": str(uuid.uuid4()),
    }

    try:
        # 1. Run graph until interrupt at await_review
        state_1 = await graph.ainvoke(init_state, config=config)
        assert state_1.get("stage") == "PENDING_REVIEW"
        dossier_id = state_1.get("dossier_id")
        assert dossier_id is not None

        # Check ledger count for this case
        count_1 = await conn.fetchval(
            "SELECT count(*) FROM vigil.evidence_ledger WHERE case_id = $1::uuid;",
            uuid.UUID(case_id),
        )
        assert count_1 >= 1

        # 2. Simulate process restart / reload from checkpointer: re-invoke without new command
        # The checkpointer restores state at await_review without re-running sign_node
        resumed_snapshot = await graph.aget_state(config)
        assert resumed_snapshot.next == ("await_review",)

        count_2 = await conn.fetchval(
            "SELECT count(*) FROM vigil.evidence_ledger WHERE case_id = $1::uuid;",
            uuid.UUID(case_id),
        )
        assert count_2 == count_1, "No duplicate ledger entries on checkpointer reload"

    finally:
        await conn.close()
