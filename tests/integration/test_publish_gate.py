from __future__ import annotations

import pytest
from orchestrator.models import CaseState
from orchestrator.nodes import OrchestratorDeps, publish_node


@pytest.mark.asyncio
async def test_cannot_reach_published_without_compliance_approval() -> None:
    # AC-DOS-06: Cannot reach PUBLISHED without compliance approval (409)
    deps = OrchestratorDeps()
    node = publish_node(deps)

    # 1. State without approval (e.g. NOT_REVIEWED or REJECTED)
    state_unapproved: CaseState = {
        "case_id": "case_gate_test_01",
        "symbol": "ZENITHSME",
        "review": {"status": "NOT_REVIEWED"},
    }

    with pytest.raises(ValueError) as exc_info:
        await node(state_unapproved)
    assert "409" in str(exc_info.value) or "approval" in str(exc_info.value).lower()

    # 2. State with APPROVED review succeeds
    state_approved: CaseState = {
        "case_id": "case_gate_test_01",
        "symbol": "ZENITHSME",
        "review": {"status": "APPROVED", "reviewer": "officer_1", "comment": "Verified"},
    }
    result = await node(state_approved)
    assert result.get("stage") == "PUBLISHED"
