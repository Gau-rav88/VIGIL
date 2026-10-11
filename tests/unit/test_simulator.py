import numpy as np
import pytest
from simulator.market_model import MarketModel
from simulator.orderbook import OrderBook
from simulator.ring import build_ring


def test_orderbook_matching() -> None:
    ob = OrderBook(symbol="ZENITHSME")
    seller_acc = "acc_seller_00000000001"  # 22 chars
    buyer_acc = "acc_buyer_000000000001"   # 22 chars

    # Add resting ask
    l3_sell, trades_sell = ob.add_order(
        order_id="O-ASK-1",
        side="SELL",
        price=40.50,
        qty=100,
        account_id=seller_acc,
        broker_id="BRK-01",
        ts_exchange="2026-03-14T04:30:00Z",
    )
    assert len(l3_sell) == 1
    assert len(trades_sell) == 0
    assert ob.best_ask() == 40.50

    # Add crossing buy
    l3_buy, trades_buy = ob.add_order(
        order_id="O-BUY-1",
        side="BUY",
        price=40.50,
        qty=100,
        account_id=buyer_acc,
        broker_id="BRK-02",
        ts_exchange="2026-03-14T04:30:01Z",
    )
    assert len(trades_buy) == 1
    trade = trades_buy[0]
    assert trade.price == "40.50"
    assert trade.qty == 100
    assert trade.buyer.account_id == buyer_acc
    assert trade.seller.account_id == seller_acc
    assert ob.best_ask() is None


def test_orderbook_l2_snapshot() -> None:
    ob = OrderBook(symbol="ZENITHSME")
    acc1 = "acc_000000000000000001"
    acc2 = "acc_000000000000000002"
    acc3 = "acc_000000000000000003"

    ob.add_order("O-B1", "BUY", 40.0, 50, acc1, "BRK-01", "2026-03-14T04:00:00Z")
    ob.add_order("O-B2", "BUY", 39.9, 100, acc2, "BRK-01", "2026-03-14T04:00:00Z")
    ob.add_order("O-A1", "SELL", 40.1, 75, acc3, "BRK-02", "2026-03-14T04:00:00Z")

    snap = ob.get_l2_snapshot("2026-03-14T04:00:00Z", depth_levels=5)
    assert snap.symbol == "ZENITHSME"
    assert len(snap.bids) == 2
    assert snap.bids[0] == ["40.00", 50, 1]
    assert snap.bids[1] == ["39.90", 100, 1]
    assert len(snap.asks) == 1
    assert snap.asks[0] == ["40.10", 75, 1]


def test_ring_generation_determinism() -> None:
    cfg = {
        "ring": {
            "accounts": 10,
            "brokers": 2,
            "shared_devices": 3,
            "shared_asn": 1,
            "wash_cycles": {"count": 2, "lengths": [2, 3], "qty": 500},
        }
    }
    rng1 = np.random.default_rng(np.random.PCG64(42))
    ring1 = build_ring(cfg, rng1)
    assert ring1 is not None
    assert len(ring1.accounts) == 10

    rng2 = np.random.default_rng(np.random.PCG64(42))
    ring2 = build_ring(cfg, rng2)
    assert ring2 is not None

    acc_ids_1 = [a.account_id for a in ring1.accounts]
    acc_ids_2 = [a.account_id for a in ring2.accounts]
    assert acc_ids_1 == acc_ids_2


def test_market_model_determinism() -> None:
    cfg = {"id": "test_scenario", "duration_s": 60}
    rng1 = np.random.default_rng(np.random.PCG64(123))
    m1 = MarketModel(rng=rng1, scenario_cfg=cfg)
    l3_1, trades_1, _ = m1.generate_step(0.0, 0.25, "2026-03-14T04:30:00.000000Z")

    rng2 = np.random.default_rng(np.random.PCG64(123))
    m2 = MarketModel(rng=rng2, scenario_cfg=cfg)
    l3_2, trades_2, _ = m2.generate_step(0.0, 0.25, "2026-03-14T04:30:00.000000Z")

    assert len(l3_1) == len(l3_2)
    assert len(trades_1) == len(trades_2)
    if trades_1:
        assert trades_1[0].price == trades_2[0].price
        assert trades_1[0].qty == trades_2[0].qty


@pytest.mark.asyncio
async def test_simulator_start_fails_clearly_with_no_subscribers() -> None:
    from simulator.scenarios import ScenarioManager

    mgr = ScenarioManager()
    with pytest.raises(RuntimeError, match="timed out after 0.1s waiting for subscriber"):
        await mgr.start("baseline_01", speed=10.0, wait_subscribers_s=0.1)

    assert not mgr.running
    status = mgr.get_status()
    assert status["running"] is False
    assert status["active_market_clients"] == 0
    assert status["active_social_clients"] == 0
    assert "epoch" in status
    assert "dropped_frames" in status


@pytest.mark.asyncio
async def test_simulator_start_succeeds_with_subscribers() -> None:
    import asyncio

    from simulator.scenarios import ScenarioManager

    mgr = ScenarioManager()
    q_market: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    q_social: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    mgr.market_subscribers.add(q_market)
    mgr.social_subscribers.add(q_social)

    res = await mgr.start("baseline_01", speed=10.0, wait_subscribers_s=0.5)
    assert res["status"] == "started"
    assert "epoch" in res
    assert mgr.running is True

    await mgr.stop()
    assert mgr.running is False
