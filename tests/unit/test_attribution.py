from __future__ import annotations

import numpy as np
import pytest
from attribution.community import CommunityDetector
from attribution.confidence import (
    calculate_pair_confidence,
)
from attribution.cycles import CycleDetector
from attribution.engine import AttributionEngine
from attribution.export import CytoscapeExporter
from attribution.graph_store import Neo4jGraphStore
from attribution.link_methods import LinkMethodEvaluator
from attribution.models import (
    AccountPairLink,
    EntityCluster,
    LinkMethod,
    MethodScore,
)
from attribution.reaction import ReactionLatencyAnalyzer


def test_calculate_pair_confidence_noisy_or() -> None:
    score_kyc = MethodScore(method=LinkMethod.SHARED_KYC, weight=0.95, strength=1.0)
    conf_1 = calculate_pair_confidence([score_kyc])
    assert pytest.approx(conf_1, 0.001) == 0.95

    score_dev = MethodScore(method=LinkMethod.SHARED_DEVICE, weight=0.90, strength=0.8)
    conf_2 = calculate_pair_confidence([score_kyc, score_dev])
    assert pytest.approx(conf_2, 0.001) == 0.986
    assert calculate_pair_confidence([]) == 0.0


def test_link_methods_evaluation() -> None:
    eval = LinkMethodEvaluator()

    # KYC
    s_kyc = eval.eval_shared_kyc({"phone_hash": "h1"}, {"phone_hash": "h1"})
    assert s_kyc is not None and s_kyc.strength == 1.0
    assert eval.eval_shared_kyc({"phone_hash": "h1"}, {"phone_hash": "h2"}) is None

    # Device
    s_dev = eval.eval_shared_device(["dev_1", "dev_2"])
    assert s_dev is not None and s_dev.strength == 0.8
    assert eval.eval_shared_device([]) is None

    # Cycles
    s_cyc = eval.eval_circular_cycle(3)
    assert s_cyc is not None and s_cyc.strength == 1.0

    # Sync orders
    s_sync = eval.eval_synchronized_orders(best_p=0.002, co_orders=5)
    assert s_sync is not None and s_sync.strength == 0.8

    # Network
    s_net_ip = eval.eval_shared_network(ip_match=True, same_asn=True, same_gateway=True)
    assert s_net_ip is not None and s_net_ip.strength == 1.0

    s_net_asn = eval.eval_shared_network(ip_match=False, same_asn=True, same_gateway=True)
    assert s_net_asn is not None and s_net_asn.strength == 0.5

    # Broker pathway
    s_bp = eval.eval_broker_pathway("BRK-01", "GW-1", 0.85, "BRK-01", "GW-1", 0.90)
    assert s_bp is not None and s_bp.strength == 1.0


def test_latency_signature_ks() -> None:
    eval = LinkMethodEvaluator()
    rng = np.random.default_rng(42)
    data_a = rng.normal(10.0, 1.0, 60).tolist()
    data_b = rng.normal(10.0, 1.0, 60).tolist()
    res = eval.eval_latency_signature(data_a, data_b)
    assert res is not None
    assert res.strength > 0.0


def test_reaction_latency_analyzer() -> None:
    analyzer = ReactionLatencyAnalyzer(n_ref_samples=50, p_threshold=0.05)
    ctas = [1000, 5000, 10000, 15000]
    orders = [1100, 5100, 10100, 15100]
    res = analyzer.analyze_trader_reaction(ctas, orders, 0, 20000)
    assert res is not None
    assert res["median_latency_s"] == 0.1
    assert res["confidence"] >= 0.60


def test_cycle_detector_basic() -> None:
    detector = CycleDetector(min_len=2, max_len=4, qty_tol=0.05)
    trades = [
        {"seller": "A", "buyer": "B", "qty": 1000, "price": 40.0, "ts_ms": 1000, "trade_id": "T1"},
        {"seller": "B", "buyer": "C", "qty": 1000, "price": 40.0, "ts_ms": 2000, "trade_id": "T2"},
        {"seller": "C", "buyer": "A", "qty": 1000, "price": 40.0, "ts_ms": 3000, "trade_id": "T3"},
    ]
    cycles = detector.find_cycles(trades)
    assert len(cycles) == 1
    assert cycles[0].length == 3
    assert set(cycles[0].accounts) == {"A", "B", "C"}
    assert cycles[0].cycle_volume == 3000


def test_community_resolution_and_ring_score() -> None:
    cd = CommunityDetector()
    link1 = AccountPairLink(
        source_account="acc_01",
        target_account="acc_02",
        confidence=0.85,
        methods=[LinkMethod.SHARED_DEVICE],
        method_scores=[MethodScore(method=LinkMethod.SHARED_DEVICE, weight=0.90, strength=0.8)],
        is_finding=True,
    )
    link2 = AccountPairLink(
        source_account="acc_02",
        target_account="acc_03",
        confidence=0.85,
        methods=[LinkMethod.SHARED_DEVICE],
        method_scores=[MethodScore(method=LinkMethod.SHARED_DEVICE, weight=0.90, strength=0.8)],
        is_finding=True,
    )
    link_lead = AccountPairLink(
        source_account="acc_03",
        target_account="acc_04",
        confidence=0.45,
        methods=[LinkMethod.BROKER_PATHWAY],
        method_scores=[MethodScore(method=LinkMethod.BROKER_PATHWAY, weight=0.40, strength=0.5)],
        is_finding=False,
    )

    clusters = cd.resolve_entities(
        links=[link1, link2, link_lead],
        account_volumes={"acc_01": 1000, "acc_02": 1000, "acc_03": 1000, "acc_04": 200},
        total_symbol_volume=6000,
        device_map={"acc_01": ["dev_1"], "acc_02": ["dev_1"], "acc_03": ["dev_1"]},
        broker_map={"acc_01": "BRK-01", "acc_02": "BRK-01", "acc_03": "BRK-01"},
        asn_map={"acc_01": 55836, "acc_02": 55836, "acc_03": 55836},
    )

    assert len(clusters) == 1
    c = clusters[0]
    assert set(c.accounts) == {"acc_01", "acc_02", "acc_03"}
    assert c.ring_score > 0.50
    assert c.volume_share == pytest.approx(3000 / 6000, 0.01)
    assert len(c.findings_links) == 2
    assert len(c.leads_links) == 1


def test_cytoscape_exporter() -> None:
    exporter = CytoscapeExporter()
    cluster = EntityCluster(
        entity_id="001",
        accounts=["acc_01", "acc_02"],
        ring_score=0.92,
        volume_share=0.45,
        brokers=["BRK-01"],
        shared_devices=["dev_1"],
        findings_links=[
            AccountPairLink(
                source_account="acc_01",
                target_account="acc_02",
                confidence=0.85,
                methods=[LinkMethod.SHARED_DEVICE],
                is_finding=True,
            )
        ],
    )
    graph = exporter.export_cluster(cluster)
    assert len(graph.nodes) >= 3
    assert any(n.data.type == "Entity" for n in graph.nodes)
    assert any(e.data.type == "LINKED" for e in graph.edges)

    # Export from records
    records = [
        {"a": {"account_id": "acc_01"}, "links": [{"source": "acc_01", "target": "acc_02", "confidence": 0.85}]}
    ]
    g2 = exporter.export_from_records(records)
    assert len(g2.nodes) == 1
    assert len(g2.edges) == 1


def test_attribution_engine_full() -> None:
    store = Neo4jGraphStore(uri="bolt://localhost:7687")
    engine = AttributionEngine(graph_store=store)

    trades = [
        {
            "seller": "TRADER_A",
            "buyer": "TRADER_B",
            "qty": 1000,
            "price": 40.0,
            "ts_ms": 1000,
            "trade_id": "T1",
            "seller_device_fp": "D1",
            "buyer_device_fp": "D1",
            "seller_asn": 55836,
            "buyer_asn": 55836,
            "seller_broker_id": "BRK-1",
            "buyer_broker_id": "BRK-1",
            "seller_gateway_id": "GW-1",
            "buyer_gateway_id": "GW-1",
        },
        {
            "seller": "TRADER_B",
            "buyer": "TRADER_A",
            "qty": 1000,
            "price": 40.0,
            "ts_ms": 2000,
            "trade_id": "T2",
            "seller_device_fp": "D1",
            "buyer_device_fp": "D1",
            "seller_asn": 55836,
            "buyer_asn": 55836,
            "seller_broker_id": "BRK-1",
            "buyer_broker_id": "BRK-1",
            "seller_gateway_id": "GW-1",
            "buyer_gateway_id": "GW-1",
        },
    ]

    ctas = [{"ts_ms": 500}]
    kyc = {
        "TRADER_A": {"phone_hash": "P1"},
        "TRADER_B": {"phone_hash": "P1"},
    }
    syncs = [{"a": "TRADER_A", "b": "TRADER_B", "best_p": 0.001, "co_orders": 4}]

    links, entities, cycles = engine.attribute_accounts(
        trades=trades,
        symbol="ZENITHSME",
        cta_events=ctas,
        known_kyc=kyc,
        sync_pairs=syncs,
    )

    assert len(links) == 1
    assert links[0].confidence > 0.90
    assert links[0].is_finding
    assert len(entities) == 1
    assert entities[0].ring_score > 0.90
    assert len(cycles) == 1

    # Test create_anomaly_events
    anoms = engine.create_anomaly_events(
        symbol="ZENITHSME",
        entities=entities,
        cycles=cycles,
        window_start_iso="2026-03-14T04:30:00Z",
        window_end_iso="2026-03-14T04:40:00Z",
    )
    assert len(anoms) >= 2
    types = {a.type for a in anoms}
    assert "CIRCULAR_RING" in types
    assert "FINGERPRINT_CLUSTER" in types

    # Test export_subgraph
    subg = engine.export_subgraph(entities[0])
    assert len(subg.nodes) >= 3


@pytest.mark.asyncio
async def test_neo4j_graph_store_in_memory_and_veto() -> None:
    store = Neo4jGraphStore(uri="bolt://invalid-host:9999")
    # Will fail connection and switch to degraded mode
    connected = await store.connect()
    assert not connected
    assert store.degraded_mode

    # Test in-memory trade upsert
    trades = [
        {"seller": "S1", "buyer": "B1", "qty": 100, "price": 40.0, "ts_ms": 1000, "trade_id": "T100"}
    ]
    await store.upsert_traders_and_trades(trades, symbol="ZENITHSME")
    assert store.fallback_nx.number_of_nodes() == 2
    assert store.fallback_nx.number_of_edges() == 1

    # Test veto in degraded mode
    assert not store.is_vetoed("S1", "B1")
    await store.record_veto("S1", "B1")
    assert store.is_vetoed("S1", "B1")

    # Test get_case_subgraph fallback
    subgraph = await store.get_case_subgraph("case_test")
    assert len(subgraph["nodes"]) == 2
    assert subgraph["degraded"]

    await store.close()


@pytest.mark.asyncio
async def test_neo4j_graph_store_connected() -> None:
    store = Neo4jGraphStore(uri="bolt://localhost:7687")
    try:
        conn = await store.connect()
        if conn:
            import uuid
            case_id = f"case_test_live_{uuid.uuid4().hex[:8]}"
            trades = [
                {
                    "seller": "ACC_TEST_S",
                    "buyer": "ACC_TEST_B",
                    "qty": 500,
                    "price": 40.0,
                    "ts_ms": 1000,
                    "trade_id": "T_LIVE_1",
                    "seller_device_fp": "D_TEST",
                    "buyer_device_fp": "D_TEST",
                    "seller_asn": 55836,
                    "buyer_asn": 55836,
                    "seller_broker_id": "BRK-T",
                    "buyer_broker_id": "BRK-T",
                }
            ]
            await store.upsert_traders_and_trades(trades, symbol="ZENITHSME")
            links = [
                {
                    "source_account": "ACC_TEST_S",
                    "target_account": "ACC_TEST_B",
                    "confidence": 0.88,
                    "methods": ["SHARED_DEVICE"],
                    "evidence_ids": ["dev_D_TEST"],
                }
            ]
            await store.upsert_linked_edges(links, case_id=case_id)
            subg = await store.get_case_subgraph(case_id)
            assert len(subg["nodes"]) >= 2
            assert len(subg["edges"]) >= 1

            # Test veto
            await store.record_veto("ACC_TEST_S", "ACC_TEST_B", case_id=case_id)
            assert store.is_vetoed("ACC_TEST_S", "ACC_TEST_B", case_id=case_id)
    finally:
        await store.close()


def test_attribution_service_initialization() -> None:
    from attribution.main import AttributionService
    svc = AttributionService()
    assert "ZENITHSME" in svc.watchlist_symbols
    assert len(svc.config_hash) == 64
    assert not svc.running

