from __future__ import annotations

import io
import os
import zipfile


def is_demo_enabled() -> bool:
    return os.getenv("DEMO_FIXTURES", "false").lower() in ("true", "1")

DEMO_ANOMALIES = [
    {
        "anomaly_id": "00000000-0000-0000-0000-000000000001",
        "type": "CROSS_MODAL_ALIGNMENT",
        "source_agent": "alignment_engine",
        "symbol": "DEMO_TICKER",
        "score": 0.88,
        "severity": "CRITICAL",
        "metrics": {"xcorr_peak": 0.72, "p_value": 0.005, "lag_s": 120.0},
        "detected_at": "2026-03-14T05:00:00Z",
        "data_source": "demo_fixture",
    }
]

DEMO_TRADES = [
    {
        "ts": "2026-03-14T04:45:00Z",
        "event_id": "00000000-0000-0000-0000-000000000002",
        "trade_id": "T-DEMO-001",
        "seq": 1,
        "price": 100.0,
        "qty": 500,
        "aggressor_side": "BUY",
        "buyer_account": "demo_acc_01",
        "seller_account": "demo_acc_02",
        "is_synthetic": True,
        "data_source": "demo_fixture",
    },
    {
        "ts": "2026-03-14T04:55:00Z",
        "event_id": "00000000-0000-0000-0000-000000000003",
        "trade_id": "T-DEMO-002",
        "seq": 2,
        "price": 105.0,
        "qty": 1000,
        "aggressor_side": "BUY",
        "buyer_account": "demo_acc_03",
        "seller_account": "demo_acc_01",
        "is_synthetic": True,
        "data_source": "demo_fixture",
    },
]

DEMO_CASES = [
    {
        "case_id": "00000000-0000-0000-0000-000000000010",
        "symbol": "DEMO_TICKER",
        "exchange": "SYNTH",
        "status": "PENDING_REVIEW",
        "window_start": "2026-03-14T04:00:00Z",
        "window_end": "2026-03-14T05:00:00Z",
        "created_at": "2026-03-14T05:01:00Z",
        "updated_at": "2026-03-14T05:01:00Z",
        "overall_confidence": 0.92,
        "completeness": 0.88,
        "data_source": "demo_fixture",
    }
]

DEMO_SIGNALS = [
    {
        "signal_id": "00000000-0000-0000-0000-000000000020",
        "ts": "2026-03-14T04:40:00Z",
        "ticker": "DEMO_TICKER",
        "platform": "Telegram",
        "channel_id": "demo_pump_channel",
        "author_id": "demo_admin",
        "cta_class": "BUY_RECOMMENDATION",
        "confidence": 0.95,
        "raw_text": "Demo buy signal for test purposes",
        "data_source": "demo_fixture",
    }
]

def make_demo_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", '{"data_source":"demo_fixture"}')
    return buf.getvalue()

DEMO_BUNDLE_BYTES = make_demo_zip()
