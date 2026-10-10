from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from social_ingest.main import SocialIngester


@pytest.mark.asyncio
async def test_zero_raw_handles_or_message_ids_stored() -> None:
    """
    Acceptance Criterion P3-G3:
    No raw handle or message id appears in any stored/published row.
    Handles/ids are transformed to deterministic HMAC pseudonyms.
    """
    ingester = SocialIngester()
    mock_producer = AsyncMock()
    ingester.producer = mock_producer

    emitted_records: list[dict[str, str]] = []

    async def mock_send(topic: str, value: bytes, key: bytes | None = None) -> None:
        if topic == "social.messages.raw":
            emitted_records.append(json.loads(value.decode("utf-8")))

    mock_producer.send.side_effect = mock_send

    sensitive_handles = [
        "@operator_vip_pump",
        "@insider_trader_42",
        "john_doe_personal_handle",
        "+919876543210",
        "user_secret_account",
    ]
    raw_message_ids = [
        "raw_msg_id_999901",
        "raw_msg_id_999902",
        "raw_msg_id_999903",
        "raw_msg_id_999904",
        "raw_msg_id_999905",
    ]

    for idx, (handle, msg_id) in enumerate(zip(sensitive_handles, raw_message_ids, strict=False)):
        raw_msg = json.dumps({
            "event_id": f"20000000-0000-0000-0000-{idx:012d}",
            "platform": "telegram",
            "channel_id": "tg-pump-elite",
            "channel_name": "Elite Wealth Pumps",
            "channel_visibility": "public",
            "message_id": msg_id,
            "author_id": handle,
            "ts_posted": "2026-10-10T12:00:00Z",
            "text": "Discussion on $ZENITHSME breakout buy now",
            "is_synthetic": True,
        })
        await ingester._process_message(raw_msg)

    assert len(emitted_records) == len(sensitive_handles)

    for idx, (handle, msg_id) in enumerate(zip(sensitive_handles, raw_message_ids, strict=False)):
        record = emitted_records[idx]

        # 1. Raw handle must NOT appear anywhere in the stored record's author_id or other fields
        assert handle not in record["author_id"], f"Raw handle leaked in author_id: {record['author_id']}"
        assert handle not in json.dumps(record), f"Raw handle {handle} leaked in record json"

        # 2. Raw message id must NOT appear in message_id or other fields
        assert msg_id not in record["message_id"], f"Raw msg_id leaked in message_id: {record['message_id']}"

        # 3. Both author_id and message_id must be valid HMAC pseudonyms (22-char base64url)
        assert len(record["author_id"]) == 22, f"Author pseudonym should be 22 chars: {record['author_id']}"
        assert len(record["message_id"]) == 22, f"Message pseudonym should be 22 chars: {record['message_id']}"

        # 4. Check base64url characters
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in record["author_id"])
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in record["message_id"])
