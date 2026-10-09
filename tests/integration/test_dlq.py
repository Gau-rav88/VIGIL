from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock

import pytest
from market_ingest.main import MarketIngester


@pytest.mark.asyncio
async def test_dlq_100_malformed_events() -> None:
    ingester = MarketIngester()
    mock_producer = AsyncMock()
    ingester.producer = mock_producer

    dlq_records: list[dict[str, str]] = []

    async def mock_send(topic: str, value: bytes, key: bytes | None = None) -> None:
        if topic == "dlq.market":
            dlq_records.append(json.loads(value.decode("utf-8")))

    mock_producer.send.side_effect = mock_send

    # Generate 100 distinctly malformed messages across multiple categories
    malformed_payloads: list[str] = []

    # Category 1: Invalid JSON (25 messages)
    for i in range(25):
        malformed_payloads.append(f'{{"broken_json": {i}, "unclosed_string: "abc')

    # Category 2: Missing kind or data (25 messages)
    for i in range(25):
        malformed_payloads.append(json.dumps({"wrong_envelope": i}))

    # Category 3: Invalid trade schema - missing required fields or bad types (25 messages)
    for i in range(25):
        malformed_payloads.append(json.dumps({
            "kind": "trade",
            "data": {
                "event_id": f"not-a-uuid-{i}",
                "symbol": "ZENITHSME",
                "price": "not_a_valid_price",  # schema expects regex pattern
            }
        }))

    # Category 4: Unrecognized event kind (25 messages)
    for i in range(25):
        malformed_payloads.append(json.dumps({
            "kind": f"unrecognized_market_event_{i}",
            "data": {"some_field": 123}
        }))

    assert len(malformed_payloads) == 100

    # Inject all 100 malformed events
    for raw in malformed_payloads:
        await ingester._process_message(raw)

    # Acceptance Criterion AC-ING-02:
    # 100 malformed events -> exactly 100 DLQ records with non-empty error
    assert len(dlq_records) == 100, f"Expected 100 DLQ records, got {len(dlq_records)}"
    assert ingester.stats["dlq"] == 100

    for idx, record in enumerate(dlq_records):
        assert record["stage"] == "market_ingest"
        assert record["error"] and len(record["error"].strip()) > 0, f"Record {idx} has empty error"
        assert "ts" in record

        # Verify original_b64 decodes back to original input
        raw_decoded = base64.b64decode(record["original_b64"]).decode("utf-8")
        assert raw_decoded == malformed_payloads[idx]
