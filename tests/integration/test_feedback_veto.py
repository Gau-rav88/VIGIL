from __future__ import annotations

import uuid

import pytest
from attribution.engine import AttributionEngine
from attribution.graph_store import Neo4jGraphStore


@pytest.mark.asyncio
async def test_feedback_veto_prevents_link_recreation() -> None:
    # P5-G1: A rejected link is never recreated after a re-run
    store = Neo4jGraphStore(uri="bolt://localhost:7687")
    await store.connect()

    engine = AttributionEngine(graph_store=store)

    uid = uuid.uuid4().hex[:8]
    acc_1 = f"VETO_ACC_1_{uid}"
    acc_2 = f"VETO_ACC_2_{uid}"
    case_id = f"case_veto_{uid}"

    trades = [
        {
            "seller": acc_1,
            "buyer": acc_2,
            "qty": 500,
            "price": 40.0,
            "ts_ms": 1000,
            "trade_id": f"T_VETO_1_{uid}",
            "seller_device_fp": f"DEV_SHARED_{uid}",
            "buyer_device_fp": f"DEV_SHARED_{uid}",
        },
        {
            "seller": acc_2,
            "buyer": acc_1,
            "qty": 500,
            "price": 40.0,
            "ts_ms": 2000,
            "trade_id": f"T_VETO_2_{uid}",
            "seller_device_fp": f"DEV_SHARED_{uid}",
            "buyer_device_fp": f"DEV_SHARED_{uid}",
        },
    ]

    # 1. Initial attribution: Accounts share device and cycle -> linked!
    links_1, entities_1, _ = engine.attribute_accounts(trades=trades, symbol="ZENITHSME", case_id=case_id)
    matched_links_1 = [
        lk for lk in links_1
        if set([lk.source_account, lk.target_account]) == {acc_1, acc_2}
    ]
    assert len(matched_links_1) == 1
    assert matched_links_1[0].confidence >= 0.60
    assert matched_links_1[0].is_finding

    # 2. Investigator issues REJECT feedback (storing persistent veto)
    await store.record_veto(acc_1, acc_2, case_id=case_id)
    assert store.is_vetoed(acc_1, acc_2, case_id=case_id)

    # 3. Re-run attribution on identical dataset
    links_2, entities_2, _ = engine.attribute_accounts(trades=trades, symbol="ZENITHSME", case_id=case_id)
    matched_links_2 = [
        lk for lk in links_2
        if set([lk.source_account, lk.target_account]) == {acc_1, acc_2}
    ]

    # Must be completely suppressed and NOT recreated!
    assert len(matched_links_2) == 0, "Rejected link must never be recreated"

    await store.close()

