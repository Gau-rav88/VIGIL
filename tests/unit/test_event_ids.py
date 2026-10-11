from __future__ import annotations

import uuid

from vigil_common.ids import to_event_uuid


def test_valid_uuid_passes_through_unchanged() -> None:
    original = uuid.uuid4()
    converted = to_event_uuid("binance", str(original))
    assert converted == original
    assert to_event_uuid("binance", original) == original


def test_deterministic_conversion_for_string_ids() -> None:
    raw_id = "binance-trade-987654321"
    u1 = to_event_uuid("binance", raw_id)
    u2 = to_event_uuid("binance", raw_id)
    assert u1 == u2
    assert isinstance(u1, uuid.UUID)
    assert u1.version == 5


def test_distinct_sources_or_ids_do_not_collide() -> None:
    u_binance = to_event_uuid("binance", "msg-100")
    u_telegram = to_event_uuid("telegram", "msg-100")
    u_discord = to_event_uuid("discord", "msg-100")
    u_other_id = to_event_uuid("binance", "msg-101")

    assert u_binance != u_telegram
    assert u_binance != u_discord
    assert u_telegram != u_discord
    assert u_binance != u_other_id


def test_signals_reference_same_uuid_as_message() -> None:
    msg_raw_id = "tg-pump-alert-42"
    platform = "telegram"

    # Message sink generates UUID
    msg_uuid = to_event_uuid(platform, msg_raw_id)
    # Signal referencing the same source message ID
    signal_ref_uuid = to_event_uuid(platform, msg_raw_id)

    assert msg_uuid == signal_ref_uuid
