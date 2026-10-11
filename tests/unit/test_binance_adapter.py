from __future__ import annotations

import json

from market_ingest.binance_adapter import BinanceMarketAdapter


def test_binance_adapter_no_shared_accounts_across_trades() -> None:
    adapter = BinanceMarketAdapter(["BTCUSDT"])

    msg1 = json.dumps({
        "stream": "btcusdt@trade",
        "data": {
            "s": "BTCUSDT",
            "t": 1001,
            "p": "65000.50",
            "q": "0.15",
            "T": 1710390600000,
            "m": False,
            "b": 555,
            "a": 777,
        },
    })

    msg2 = json.dumps({
        "stream": "btcusdt@trade",
        "data": {
            "s": "BTCUSDT",
            "t": 1002,
            "p": "65001.00",
            "q": "0.20",
            "T": 1710390601000,
            "m": True,
            "b": 555,  # Same order ID!
            "a": 777,  # Same order ID!
        },
    })

    frame1 = adapter._normalize_frame(msg1)
    frame2 = adapter._normalize_frame(msg2)

    assert frame1 is not None and frame2 is not None
    trade1 = frame1["data"]
    trade2 = frame2["data"]

    # Even with same order IDs in public Binance feed, accounts must be per-trade anon_ tokens
    b1_acc = trade1["buyer"]["account_id"]
    s1_acc = trade1["seller"]["account_id"]
    b2_acc = trade2["buyer"]["account_id"]
    s2_acc = trade2["seller"]["account_id"]

    assert b1_acc.startswith("anon_")
    assert s1_acc.startswith("anon_")
    assert b2_acc.startswith("anon_")
    assert s2_acc.startswith("anon_")

    # Length check: "anon_" (5) + 24 hex = 29
    assert len(b1_acc) == 29
    assert len(s1_acc) == 29

    # No shared accounts across distinct trades
    assert b1_acc != b2_acc
    assert s1_acc != s2_acc
    assert b1_acc != s1_acc

    # Order IDs must still be preserved in Party.order_id
    assert trade1["buyer"]["order_id"] == "555"
    assert trade1["seller"]["order_id"] == "777"

    # Must be marked synthetic
    assert trade1["is_synthetic"] is True
    assert trade2["is_synthetic"] is True
