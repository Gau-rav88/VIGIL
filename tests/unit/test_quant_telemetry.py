from unittest.mock import AsyncMock, patch

import pytest
from quant_telemetry.detectors import (
    PriceJumpDetector,
    SpoofingLayeringDetector,
    SpreadDepthDetector,
    SynchronizedOrdersDetector,
    VolumeSpikeDetector,
    WashCycleDetector,
)
from quant_telemetry.engine import QuantTelemetryEngine
from quant_telemetry.main import QuantTelemetryService


def test_volume_spike_detector() -> None:
    detector = VolumeSpikeDetector()
    sym = "ZENITHSME"

    # Feed baseline traffic: 50 bins of 100 units each (5 seconds per bin)
    t = 1000.0
    for _ in range(50):
        ev = {
            "symbol": sym,
            "ts_exchange": t,
            "qty": 100,
            "trade_id": f"T-BASE-{int(t)}",
            "buyer": {"account_id": "ACC-1"},
            "seller": {"account_id": "ACC-2"},
        }
        res = detector.on_event("trade", ev)
        assert len(res) == 0
        t += 5.0

    # Feed a massive volume spike lasting 4 consecutive bins (10,000 units per bin)
    spikes = []
    for _ in range(4):
        ev = {
            "symbol": sym,
            "ts_exchange": t,
            "qty": 10000,
            "trade_id": f"T-SPIKE-{int(t)}",
            "buyer": {"account_id": "ACC-PUMP"},
            "seller": {"account_id": "ACC-2"},
        }
        res = detector.on_event("trade", ev)
        if res:
            spikes.extend(res)
        t += 5.0

    assert len(spikes) >= 1
    anom = spikes[0]
    assert anom.type == "VOLUME_SPIKE"
    assert anom.symbol == sym
    assert anom.score >= 0.5
    assert anom.severity in ("MEDIUM", "HIGH", "CRITICAL")
    assert "z_score" in anom.metrics
    assert len(anom.evidence_refs) >= 1


def test_price_jump_detector() -> None:
    detector = PriceJumpDetector()
    sym = "TATAMOTORS"

    t = 1000.0
    # Baseline stable price at 500.0 for 2 minutes (every 5 seconds)
    for _ in range(25):
        ev = {
            "symbol": sym,
            "ts_exchange": t,
            "price": 500.0,
            "trade_id": f"T-NORM-{int(t)}",
            "buyer": {"account_id": "ACC-1"},
            "seller": {"account_id": "ACC-2"},
        }
        res = detector.on_event("trade", ev)
        assert len(res) == 0
        t += 5.0

    # Sudden 25% price jump within 60s
    jump_ev = {
        "symbol": sym,
        "ts_exchange": t,
        "price": 625.0,
        "trade_id": "T-JUMP-1",
        "buyer": {"account_id": "ACC-PUMP"},
        "seller": {"account_id": "ACC-2"},
    }
    res = detector.on_event("trade", jump_ev)
    assert len(res) == 1
    anom = res[0]
    assert anom.type == "PRICE_JUMP"
    assert anom.symbol == sym
    assert anom.score >= 0.4
    assert anom.metrics["current_price"] == 625.0
    assert anom.metrics["baseline_price"] == 500.0


def test_spread_widening_and_depth_imbalance() -> None:
    detector = SpreadDepthDetector()
    sym = "INFY"

    t = 1000.0
    # Baseline tight spread (100.00 / 100.05)
    for _ in range(30):
        ev = {
            "symbol": sym,
            "seq": 100,
            "ts_exchange": t,
            "bids": [[100.00, 500], [99.95, 500], [99.90, 500], [99.85, 500], [99.80, 500]],
            "asks": [[100.05, 500], [100.10, 500], [100.15, 500], [100.20, 500], [100.25, 500]],
        }
        res = detector.on_event("l2", ev)
        assert len(res) == 0
        t += 1.0

    # 1. Trigger SPREAD_WIDENING: spread widens to (98.00 / 104.00) => 6% spread vs baseline ~0.05%
    wide_ev = {
        "symbol": sym,
        "seq": 101,
        "ts_exchange": t,
        "bids": [[98.00, 500], [97.00, 500], [96.00, 500], [95.00, 500], [94.00, 500]],
        "asks": [[104.00, 500], [105.00, 500], [106.00, 500], [107.00, 500], [108.00, 500]],
    }
    wide_res = detector.on_event("l2", wide_ev)
    assert any(a.type == "SPREAD_WIDENING" for a in wide_res)

    # 2. Trigger DEPTH_IMBALANCE: bid depth = 10,000, ask depth = 100 for >= 10 seconds
    imb_res = []
    for _ in range(12):
        t += 1.0
        imb_ev = {
            "symbol": sym,
            "seq": 102,
            "ts_exchange": t,
            "bids": [[100.00, 2000], [99.95, 2000], [99.90, 2000], [99.85, 2000], [99.80, 2000]],
            "asks": [[100.05, 20], [100.10, 20], [100.15, 20], [100.20, 20], [100.25, 20]],
        }
        res = detector.on_event("l2", imb_ev)
        imb_res.extend(res)

    assert any(a.type == "DEPTH_IMBALANCE" for a in imb_res)


def test_spoofing_layering_detector() -> None:
    detector = SpoofingLayeringDetector()
    sym = "NOVAPHARMA"
    spoofer = "SP-001"
    t = 2000.0

    # Normal activity baseline
    for i in range(10):
        detector.on_event("l3", {
            "symbol": sym,
            "action": "NEW",
            "side": "BUY",
            "qty": 500,
            "order_id": f"O-NORM-{i}",
            "account_id": f"USER-{i}",
            "ts_exchange": t,
        })

    # Spoofer layers 6 large BUY orders
    order_ids = []
    for i in range(6):
        oid = f"O-SPOOF-{i}"
        order_ids.append(oid)
        detector.on_event("l3", {
            "symbol": sym,
            "action": "NEW",
            "side": "BUY",
            "qty": 3000,
            "order_id": oid,
            "account_id": spoofer,
            "ts_exchange": t + 0.1 * i,
        })

    # Spoofer executes aggressive opposite-side SELL trade
    detector.on_event("trade", {
        "symbol": sym,
        "trade_id": "T-SPOOF-EXEC",
        "qty": 200,
        "price": 250.0,
        "ts_exchange": t + 0.7,
        "buyer": {"account_id": "VICTIM-1"},
        "seller": {"account_id": spoofer},
    })

    # Spoofer cancels all 6 layered BUY orders
    anomalies = []
    for i, oid in enumerate(order_ids):
        res = detector.on_event("l3", {
            "symbol": sym,
            "action": "CANCEL",
            "side": "BUY",
            "qty": 3000,
            "order_id": oid,
            "account_id": spoofer,
            "ts_exchange": t + 0.8 + 0.05 * i,
        })
        if res:
            anomalies.extend(res)

    assert len(anomalies) >= 1
    anom = anomalies[0]
    assert anom.type == "SPOOFING_LAYERING"
    assert anom.symbol == sym
    assert spoofer in anom.participants
    assert anom.metrics["cancel_ratio"] >= 0.9
    assert anom.metrics["opposite_execution"] is True


def test_wash_cycle_detector() -> None:
    detector = WashCycleDetector()
    sym = "ACMESYSTEMS"
    t = 3000.0

    # 1. Self-matched trade
    self_res = detector.on_event("trade", {
        "symbol": sym,
        "ts_exchange": t,
        "trade_id": "T-SELF-1",
        "price": 120.0,
        "qty": 500,
        "buyer": {"account_id": "ACC-SAME", "device_fp": "DEV-1"},
        "seller": {"account_id": "ACC-SAME", "device_fp": "DEV-1"},
    })
    assert len(self_res) == 1
    assert self_res[0].type == "WASH_CYCLE"
    assert self_res[0].metrics["pattern"] == "SELF_MATCHED"

    # 2. 2-cycle trade: A -> B, then B -> A
    t += 20.0
    detector.on_event("trade", {
        "symbol": sym,
        "ts_exchange": t,
        "trade_id": "T-2C-1",
        "price": 120.5,
        "qty": 1000,
        "buyer": {"account_id": "ACC-B"},
        "seller": {"account_id": "ACC-A"},
    })
    t += 5.0
    res_2c = detector.on_event("trade", {
        "symbol": sym,
        "ts_exchange": t,
        "trade_id": "T-2C-2",
        "price": 120.5,
        "qty": 1000,
        "buyer": {"account_id": "ACC-A"},
        "seller": {"account_id": "ACC-B"},
    })
    assert len(res_2c) == 1
    assert res_2c[0].type == "WASH_CYCLE"
    assert res_2c[0].metrics["pattern"] == "2_CYCLE"
    assert set(res_2c[0].participants) == {"ACC-A", "ACC-B"}


def test_synchronized_orders_detector() -> None:
    detector = SynchronizedOrdersDetector()
    sym = "SOLARIS"
    t = 4000.0

    # Inject synchronized orders across multiple 500ms bins
    # Accounts ACC-SYNC-1, ACC-SYNC-2, ACC-SYNC-3 submit together in bins
    anomalies = []
    for bin_idx in range(4):
        bin_t = t + bin_idx * 1.0  # distinct bins
        for acc_id in ("ACC-SYNC-1", "ACC-SYNC-2", "ACC-SYNC-3"):
            res = detector.on_event("l3", {
                "symbol": sym,
                "action": "NEW",
                "side": "BUY",
                "qty": 100,
                "order_id": f"O-SYNC-{bin_idx}-{acc_id}",
                "account_id": acc_id,
                "ts_exchange": bin_t + 0.05,
            })
            if res:
                anomalies.extend(res)

    assert len(anomalies) >= 1
    anom = anomalies[0]
    assert anom.type == "SYNCHRONIZED_ORDERS"
    assert anom.symbol == sym
    assert anom.score >= 0.5


def test_quant_telemetry_engine_end_to_end() -> None:
    engine = QuantTelemetryEngine()
    sym = "ZENITHSME"

    trade_ev = {
        "symbol": sym,
        "ts_exchange": "2026-03-14T05:00:00.000000Z",
        "price": 40.0,
        "qty": 500,
        "trade_id": "T-ENGINE-1",
        "buyer": {"account_id": "A1"},
        "seller": {"account_id": "A2"},
    }
    anomalies = engine.process_event("trade", trade_ev)
    assert isinstance(anomalies, list)
    assert engine.total_processed == 1

    # Reload config
    engine.reload_config({"tiers": {"micro": {"volume_spike": {"z_thr": 3.0}}}})
    assert engine.config["tiers"]["micro"]["volume_spike"]["z_thr"] == 3.0


def test_wash_cycle_dfs_multicycle() -> None:
    detector = WashCycleDetector()
    sym = "ACMESYSTEMS"
    t = 5000.0

    # A -> B
    detector.on_event("trade", {
        "symbol": sym,
        "ts_exchange": t,
        "trade_id": "T-DFS-1",
        "price": 100.0,
        "qty": 500,
        "buyer": {"account_id": "ACC-B"},
        "seller": {"account_id": "ACC-A"},
    })
    # B -> C
    t += 2.0
    detector.on_event("trade", {
        "symbol": sym,
        "ts_exchange": t,
        "trade_id": "T-DFS-2",
        "price": 100.0,
        "qty": 500,
        "buyer": {"account_id": "ACC-C"},
        "seller": {"account_id": "ACC-B"},
    })
    # C -> A completes the 3-cycle!
    t += 2.0
    res = detector.on_event("trade", {
        "symbol": sym,
        "ts_exchange": t,
        "trade_id": "T-DFS-3",
        "price": 100.0,
        "qty": 500,
        "buyer": {"account_id": "ACC-A"},
        "seller": {"account_id": "ACC-C"},
    })
    assert len(res) >= 1
    assert res[0].type == "WASH_CYCLE"
    assert res[0].metrics["pattern"] == "3_CYCLE"
    assert set(res[0].participants) == {"ACC-A", "ACC-B", "ACC-C"}


@pytest.mark.asyncio
async def test_quant_telemetry_service_lifecycle() -> None:
    svc = QuantTelemetryService()
    assert svc.running is False

    mock_producer = AsyncMock()
    mock_consumer = AsyncMock()
    # Mock __aiter__ to return empty or 1 item
    record = AsyncMock()
    record.topic = "market.trades.norm"
    record.value = b'{"symbol": "TEST", "ts_exchange": "2026-03-14T00:00:00Z", "price": 10.0, "qty": 100}'
    mock_consumer.__aiter__.return_value = [record]

    with patch("quant_telemetry.main.AIOKafkaProducer", return_value=mock_producer), \
         patch("quant_telemetry.main.AIOKafkaConsumer", return_value=mock_consumer):
        task = pytest.importorskip("asyncio").create_task(svc.start())
        await pytest.importorskip("asyncio").sleep(0.05)
        await svc.stop()
        task.cancel()
        try:
            await task
        except pytest.importorskip("asyncio").CancelledError:
            pass

    assert mock_producer.start.called
    assert mock_consumer.start.called

