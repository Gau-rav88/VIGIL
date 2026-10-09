from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from market_ingest.main import MarketIngester


@pytest.mark.asyncio
async def test_injected_sequence_gap_emits_health_event() -> None:
    ingester = MarketIngester()
    mock_producer = AsyncMock()
    ingester.producer = mock_producer

    health_records: list[dict[str, str | int]] = []

    async def mock_send(topic: str, value: bytes, key: bytes | None = None) -> None:
        if topic == "health.events":
            health_records.append(json.loads(value.decode("utf-8")))

    mock_producer.send.side_effect = mock_send

    symbol = "ZENITHSME"

    def make_trade_frame(seq_num: int) -> str:
        return json.dumps({
            "kind": "trade",
            "data": {
                "schema_version": "1.0.0",
                "event_id": str(uuid.uuid4()),
                "exchange": "SYNTH",
                "symbol": symbol,
                "trade_id": f"T-GAP-{seq_num}",
                "seq": seq_num,
                "ts_exchange": "2026-03-14T05:00:00.000000Z",
                "price": "40.00",
                "qty": 100,
                "aggressor_side": "BUY",
                "buyer": {
                    "account_id": "ACC_B1_0000000000000001",
                    "broker_id": "BRK-01",
                    "gateway_id": "GW-1",
                    "order_id": f"O-B-{seq_num}",
                    "device_fp": "DEV_B1_0000000000000001",
                    "ip_hash": "IP_B1_00000000000000001",
                    "asn": 12345,
                },
                "seller": {
                    "account_id": "ACC_S1_0000000000000001",
                    "broker_id": "BRK-02",
                    "gateway_id": "GW-2",
                    "order_id": f"O-S-{seq_num}",
                    "device_fp": "DEV_S1_0000000000000001",
                    "ip_hash": "IP_S1_00000000000000001",
                    "asn": 54321,
                },
                "market_segment": "SME",
                "is_synthetic": True,
            }
        })

    # Step 1: Send trade with seq = 1 (normal start)
    await ingester._process_message(make_trade_frame(1))
    assert len(health_records) == 0, "Initial sequence number must not trigger gap event"

    # Step 2: Inject sequence gap by sending trade with seq = 5 (jumped from 1 to 5)
    await ingester._process_message(make_trade_frame(5))

    # Acceptance Criterion AC-ING-03:
    # Injected sequence gap -> one SEQ_GAP within 2 s
    assert len(health_records) == 1, f"Expected 1 SEQ_GAP health event, got {len(health_records)}"
    gap_record = health_records[0]
    assert gap_record["type"] == "SEQ_GAP"
    assert gap_record["symbol"] == symbol
    assert gap_record["expected"] == 2
    assert gap_record["received"] == 5
    assert "ts" in gap_record
    assert ingester.stats["seq_gaps"] == 1
