from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock

import pytest
from social_ingest.main import SocialIngester


@pytest.mark.asyncio
async def test_visibility_gate_rejects_non_public() -> None:
    """
    Acceptance Criterion P3-G1:
    Non-public visibility is rejected with the exact DLQ reason VISIBILITY_NOT_PERMITTED.
    """
    ingester = SocialIngester()
    mock_producer = AsyncMock()
    ingester.producer = mock_producer

    dlq_records: list[dict[str, str]] = []
    raw_records: list[dict[str, str]] = []

    async def mock_send(topic: str, value: bytes, key: bytes | None = None) -> None:
        if topic == "dlq.social":
            dlq_records.append(json.loads(value.decode("utf-8")))
        elif topic == "social.messages.raw":
            raw_records.append(json.loads(value.decode("utf-8")))

    mock_producer.send.side_effect = mock_send

    # Test various non-public visibility values
    non_public_visibilities = ["private", "invite_only", "direct_message", "secret", "restricted"]
    for idx, vis in enumerate(non_public_visibilities):
        raw_msg = json.dumps({
            "event_id": f"00000000-0000-0000-0000-{idx:012d}",
            "platform": "telegram",
            "channel_id": f"private_channel_{idx}",
            "channel_name": f"Private Group {idx}",
            "channel_visibility": vis,
            "message_id": f"msg_{idx}",
            "author_id": f"user_{idx}",
            "ts_posted": "2026-10-10T12:00:00Z",
            "text": "Secret trading call",
            "is_synthetic": True,
        })
        await ingester._process_message(raw_msg)

    # All non-public messages must be rejected and routed to dlq.social with VISIBILITY_NOT_PERMITTED
    assert len(dlq_records) == len(non_public_visibilities)
    assert len(raw_records) == 0
    assert ingester.stats["dlq"] == len(non_public_visibilities)

    for idx, record in enumerate(dlq_records):
        assert record["stage"] == "social_ingest"
        assert record["reason"] == "VISIBILITY_NOT_PERMITTED"
        assert "not permitted" in record["error"].lower()
        assert "ts" in record
        # Verify original_b64 payload can be recovered
        decoded = json.loads(base64.b64decode(record["original_b64"]).decode("utf-8"))
        assert decoded["channel_visibility"] == non_public_visibilities[idx]

    # Test allowed visibilities: public and lawful_access
    allowed_visibilities = ["public", "lawful_access"]
    for idx, vis in enumerate(allowed_visibilities):
        raw_msg = json.dumps({
            "event_id": f"10000000-0000-0000-0000-{idx:012d}",
            "platform": "telegram",
            "channel_id": f"public_channel_{idx}",
            "channel_name": f"Public Group {idx}",
            "channel_visibility": vis,
            "message_id": f"pub_msg_{idx}",
            "author_id": f"pub_user_{idx}",
            "ts_posted": "2026-10-10T12:00:00Z",
            "text": "Public stock discussion on $ZENITHSME",
            "is_synthetic": True,
        })
        await ingester._process_message(raw_msg)

    # Permitted messages should not add to DLQ and should be published to social.messages.raw
    assert len(dlq_records) == len(non_public_visibilities)
    assert len(raw_records) == 2
