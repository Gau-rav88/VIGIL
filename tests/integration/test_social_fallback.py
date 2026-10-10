from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from social_intel.engine import SocialIntelEngine


@pytest.mark.asyncio
async def test_social_fallback_when_api_key_unset() -> None:
    """
    Acceptance Criterion AC-SOC-02:
    With ANTHROPIC_API_KEY empty/unset, the pipeline runs and every signal
    has parser_mode=FALLBACK_RULES.
    """
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
        engine = SocialIntelEngine()

        test_messages = [
            {
                "event_id": "00000000-0000-0000-0000-000000000001",
                "platform": "telegram",
                "channel_id": "tg-pump-elite",
                "message_id": "m-001",
                "author_id": "auth-001",
                "text": "Bhai log $ZENITHSME me massive operator entry! Target 60.00! Buy now!",
                "ts_posted": "2026-10-10T12:00:00Z",
                "is_synthetic": True,
            },
            {
                "event_id": "00000000-0000-0000-0000-000000000002",
                "platform": "telegram",
                "channel_id": "tg-pump-elite",
                "message_id": "m-002",
                "author_id": "auth-002",
                "text": "Don't sell a single share of $ZENITHSME! Hold tight diamond hands!",
                "ts_posted": "2026-10-10T12:00:05Z",
                "is_synthetic": True,
            },
            {
                "event_id": "00000000-0000-0000-0000-000000000003",
                "platform": "telegram",
                "channel_id": "tg-pump-elite",
                "message_id": "m-003",
                "author_id": "auth-003",
                "text": "Coordinated buy order at 14:30 sharp on $ZENITHSME!",
                "ts_posted": "2026-10-10T12:00:10Z",
                "is_synthetic": True,
            },
            {
                "event_id": "00000000-0000-0000-0000-000000000004",
                "platform": "discord",
                "channel_id": "disc-traders",
                "message_id": "m-004",
                "author_id": "auth-004",
                "text": "Dump $ZENITHSME immediately! Whales are taking profit!",
                "ts_posted": "2026-10-10T12:00:15Z",
                "is_synthetic": True,
            },
            {
                "event_id": "00000000-0000-0000-0000-000000000005",
                "platform": "reddit",
                "channel_id": "reddit-investing",
                "message_id": "m-005",
                "author_id": "auth-005",
                "text": "Quarterly earnings report on ZENITHSME released today.",
                "ts_posted": "2026-10-10T12:00:20Z",
                "is_synthetic": True,
            },
        ]

        total_signals = 0
        for msg in test_messages:
            signals, _, _ = engine.process_message(msg)
            assert len(signals) >= 1
            for sig in signals:
                total_signals += 1
                # Invariant: parser mode must be FALLBACK_RULES
                assert sig.parser.mode == "FALLBACK_RULES"
                assert sig.ticker == "ZENITHSME"

        assert total_signals == len(test_messages)
