import json
from pathlib import Path

import fastjsonschema
import pytest
from pydantic import ValidationError
from vigil_common.models.anomaly import AnomalyEvent
from vigil_common.models.dossier import ForensicDossier
from vigil_common.models.market import L2Snapshot, L3OrderEvent, TradeTick
from vigil_common.models.social import SocialMessage, SocialSignal

SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "libs" / "vigil_common" / "schemas"

def load_validator(schema_name: str):
    schema_path = SCHEMAS_DIR / schema_name
    schema_dict = json.loads(schema_path.read_text(encoding="utf-8"))
    return fastjsonschema.compile(schema_dict)


# --- 1. TradeTick ---
VALID_TRADE_TICK = {
    "schema_version": "1.0.0",
    "event_id": "evt_trade_001",
    "exchange": "NSE",
    "symbol": "ZENITHSME",
    "trade_id": "trd_001",
    "seq": 100,
    "ts_exchange": "2026-10-09T10:00:00Z",
    "price": "150.25",
    "qty": 500,
    "aggressor_side": "BUY",
    "buyer": {
        "account_id": "acc_01234567890123456789",
        "broker_id": "BRK_ALPHA",
    },
    "seller": {
        "account_id": "acc_98765432109876543210",
        "broker_id": "BRK_BETA",
    },
    "is_synthetic": True,
}

INVALID_TRADE_TICK_CASES = [
    # 1. Missing required field: symbol
    {**VALID_TRADE_TICK, "symbol": None},
    # 2. Bad pattern: price with letters
    {**VALID_TRADE_TICK, "price": "150.25abc"},
    # 3. Bad enum: exchange not in allowed set
    {**VALID_TRADE_TICK, "exchange": "INVALID_EXCHANGE"},
]


# --- 2. L2Snapshot ---
VALID_L2_SNAPSHOT = {
    "schema_version": "1.0.0",
    "event_id": "evt_l2_001",
    "exchange": "NSE",
    "symbol": "ZENITHSME",
    "seq": 200,
    "ts_exchange": "2026-10-09T10:00:00Z",
    "depth_levels": 5,
    "bids": [["150.00", 100, 1], ["149.90", 200, 2], ["149.80", 300, 3], ["149.70", 400, 4], ["149.60", 500, 5]],
    "asks": [["150.10", 100, 1], ["150.20", 200, 2], ["150.30", 300, 3], ["150.40", 400, 4], ["150.50", 500, 5]],
    "is_snapshot": True,
    "is_synthetic": True,
}

INVALID_L2_SNAPSHOT_CASES = [
    # 1. Missing required field: bids
    {k: v for k, v in VALID_L2_SNAPSHOT.items() if k != "bids"},
    # 2. depth_levels out of range (< 5)
    {**VALID_L2_SNAPSHOT, "depth_levels": 2},
    # 3. Bad exchange enum
    {**VALID_L2_SNAPSHOT, "exchange": "UNKNOWN_EXCHANGE"},
]


# --- 3. L3OrderEvent ---
VALID_L3_ORDER = {
    "schema_version": "1.0.0",
    "event_id": "evt_l3_001",
    "exchange": "NSE",
    "symbol": "ZENITHSME",
    "seq": 300,
    "ts_exchange": "2026-10-09T10:00:00Z",
    "order_id": "ord_001",
    "action": "NEW",
    "side": "BUY",
    "account_id": "acc_01234567890123456789",
    "broker_id": "BRK_ALPHA",
    "is_synthetic": True,
}

INVALID_L3_ORDER_CASES = [
    # 1. Missing required field: action
    {k: v for k, v in VALID_L3_ORDER.items() if k != "action"},
    # 2. Bad action enum
    {**VALID_L3_ORDER, "action": "EXPLODE"},
    # 3. Bad account_id pattern (too short)
    {**VALID_L3_ORDER, "account_id": "short"},
]


# --- 4. SocialMessage ---
VALID_SOCIAL_MESSAGE = {
    "schema_version": "1.0.0",
    "event_id": "evt_sm_001",
    "platform": "telegram",
    "channel_id": "chan_signals_01",
    "channel_visibility": "public",
    "message_id": "msg_001",
    "author_id": "usr_01234567890123456789",
    "ts_posted": "2026-10-09T10:00:00Z",
    "text": "Target price for $ZENITHSME is 200! BUY NOW!",
    "raw_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "is_synthetic": True,
}

INVALID_SOCIAL_MESSAGE_CASES = [
    # 1. Missing required field: text
    {k: v for k, v in VALID_SOCIAL_MESSAGE.items() if k != "text"},
    # 2. Bad sha256 pattern
    {**VALID_SOCIAL_MESSAGE, "raw_sha256": "invalid_hash_not_64_chars"},
    # 3. Bad visibility enum
    {**VALID_SOCIAL_MESSAGE, "channel_visibility": "private_unlawful"},
]


# --- 5. SocialSignal ---
VALID_SOCIAL_SIGNAL = {
    "schema_version": "1.0.0",
    "signal_id": "sig_001",
    "message_event_id": "evt_sm_001",
    "platform": "telegram",
    "channel_id": "chan_signals_01",
    "author_id": "usr_01234567890123456789",
    "ts_posted": "2026-10-09T10:00:00Z",
    "ticker": "ZENITHSME",
    "ticker_confidence": 0.95,
    "cta_class": "BUY_CALL",
    "urgency": 0.9,
    "raw_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "parser": {
        "mode": "FALLBACK_RULES",
        "version": "1.0.0",
    },
}

INVALID_SOCIAL_SIGNAL_CASES = [
    # 1. Missing required field: ticker
    {k: v for k, v in VALID_SOCIAL_SIGNAL.items() if k != "ticker"},
    # 2. Bad cta_class enum
    {**VALID_SOCIAL_SIGNAL, "cta_class": "SELL_ALL_NOW_INVALID"},
    # 3. Urgency out of range (> 1.0)
    {**VALID_SOCIAL_SIGNAL, "urgency": 1.5},
]


# --- 6. AnomalyEvent ---
VALID_ANOMALY_EVENT = {
    "schema_version": "1.0.0",
    "anomaly_id": "anom_001",
    "type": "VOLUME_SPIKE",
    "source_agent": "quant_telemetry",
    "symbol": "ZENITHSME",
    "window_start": "2026-10-09T10:00:00Z",
    "window_end": "2026-10-09T10:05:00Z",
    "score": 0.88,
    "severity": "HIGH",
    "metrics": {"z_score": 4.2},
    "evidence_refs": [{"kind": "trade_id", "ref": "trd_001"}],
    "detector_version": "1.0.0",
    "config_hash": "a" * 64,
    "detected_at": "2026-10-09T10:05:01Z",
}

INVALID_ANOMALY_EVENT_CASES = [
    # 1. Missing required field: score
    {k: v for k, v in VALID_ANOMALY_EVENT.items() if k != "score"},
    # 2. Bad severity enum
    {**VALID_ANOMALY_EVENT, "severity": "APOCALYPTIC"},
    # 3. Empty evidence_refs (min_length=1)
    {**VALID_ANOMALY_EVENT, "evidence_refs": []},
]


# --- 7. ForensicDossier ---
VALID_DOSSIER = {
    "schema_version": "1.0.0",
    "dossier_id": "dos_001",
    "version": 1,
    "case_id": "case_pump_001",
    "generated_at": "2026-10-09T10:15:00Z",
    "jurisdiction": "SEBI_IN",
    "subject": {
        "symbol": "ZENITHSME",
        "exchange": "NSE",
        "window_start": "2026-10-09T10:00:00Z",
        "window_end": "2026-10-09T10:15:00Z",
        "manipulation_types": ["PUMP_AND_DUMP"],
    },
    "executive_summary": {
        "text": "Targeted SME ticker ZENITHSME experienced coordinated social pumping and rapid selling.",
        "citations": ["EV-TRADE-001"],
    },
    "timeline": [
        {
            "ts": "2026-10-09T10:00:00Z",
            "track": "SOCIAL",
            "description": "Initial burst in Telegram channel.",
            "evidence_ids": ["EV-SOC-001"],
        }
    ],
    "market_evidence": {
        "total_volume": 100000,
        "suspect_volume": 45000,
        "suspect_volume_ratio": 0.45,
        "price_move_pct": 38.5,
        "anomalies": ["anom_001"],
    },
    "social_evidence": {
        "channels": ["chan_signals_01"],
        "message_count": 42,
        "hype_peak": 85.0,
        "cta_breakdown": {"BUY_CALL": 35},
        "near_duplicate_campaigns": 2,
    },
    "attribution": {
        "rings": [
            {
                "ring_id": "ring_001",
                "entity_id": "ent_001",
                "ring_score": 0.89,
                "accounts": ["acc_01234567890123456789", "acc_98765432109876543210"],
                "methods": ["SHARED_DEVICE"],
                "cycle_count": 0,
                "net_volume": 25000,
                "evidence_ids": ["EV-GRAPH-001"],
            }
        ],
        "leads": [],
    },
    "violated_clauses": [
        {
            "regime": "SEBI",
            "clause_id": "PFUTP-4-2-a",
            "title": "Misleading appearance of trading",
            "finding_types": ["VOLUME_PUMP"],
            "rationale": "Coordinated volume expansion following social coordination.",
            "evidence_ids": ["EV-TRADE-001"],
            "legal_review_required": True,
        }
    ],
    "confidence": {
        "overall": 0.91,
        "completeness": 0.88,
        "components": {"market": 0.95, "social": 0.90, "graph": 0.88},
    },
    "limitations": ["Attribution derived from synthetic overlay."],
    "evidence_manifest": [
        {
            "evidence_id": "EV-TRADE-001",
            "type": "TRADE_SLICE",
            "sha256": "a" * 64,
            "uri": "s3://vigil-evidence/case_001/trades.json",
            "bytes": 1024,
            "captured_at": "2026-10-09T10:15:00Z",
        }
    ],
    "merkle_root": "b" * 64,
    "ledger_anchor": {
        "entry_id": 1,
        "entry_hash": "c" * 64,
        "prev_entry_hash": "0" * 64,
    },
    "signature": {
        "alg": "Ed25519",
        "key_id": "dev_key_01",
        "canonicalization": "RFC8785-JCS",
        "digest_sha256": "d" * 64,
        "value_b64": "eWVz",
        "signed_at": "2026-10-09T10:15:01Z",
    },
    "human_review": {
        "status": "NOT_REVIEWED",
    },
}

INVALID_DOSSIER_CASES = [
    # 1. Missing required field: merkle_root
    {k: v for k, v in VALID_DOSSIER.items() if k != "merkle_root"},
    # 2. Bad merkle_root pattern (not 64 hex chars)
    {**VALID_DOSSIER, "merkle_root": "bad_hex"},
    # 3. Empty timeline (min_length=1)
    {**VALID_DOSSIER, "timeline": []},
]


# ============================================================================
# Contract Tests Matrix
# ============================================================================

@pytest.mark.parametrize("schema_name,model_cls,valid_data,invalid_cases", [
    ("trade_tick.schema.json", TradeTick, VALID_TRADE_TICK, INVALID_TRADE_TICK_CASES),
    ("l2_snapshot.schema.json", L2Snapshot, VALID_L2_SNAPSHOT, INVALID_L2_SNAPSHOT_CASES),
    ("l3_order_event.schema.json", L3OrderEvent, VALID_L3_ORDER, INVALID_L3_ORDER_CASES),
    ("social_message.schema.json", SocialMessage, VALID_SOCIAL_MESSAGE, INVALID_SOCIAL_MESSAGE_CASES),
    ("social_signal.schema.json", SocialSignal, VALID_SOCIAL_SIGNAL, INVALID_SOCIAL_SIGNAL_CASES),
    ("anomaly_event.schema.json", AnomalyEvent, VALID_ANOMALY_EVENT, INVALID_ANOMALY_EVENT_CASES),
    ("forensic_dossier.schema.json", ForensicDossier, VALID_DOSSIER, INVALID_DOSSIER_CASES),
])
def test_schema_valid_and_invalid_contracts(schema_name, model_cls, valid_data, invalid_cases):
    validator = load_validator(schema_name)

    # 1. Validate valid fixture using both compiled JSON schema and Pydantic model
    assert validator(valid_data) == valid_data
    model_obj = model_cls.model_validate(valid_data)
    assert model_obj is not None

    # 2. Validate at least 3 invalid fixtures fail validation
    assert len(invalid_cases) >= 3, f"{schema_name} must have at least 3 invalid fixtures"
    for idx, invalid_data in enumerate(invalid_cases):
        failed_jsonschema = False
        failed_pydantic = False

        try:
            validator(invalid_data)
        except Exception:
            failed_jsonschema = True

        try:
            model_cls.model_validate(invalid_data)
        except (ValidationError, Exception):
            failed_pydantic = True

        assert failed_jsonschema or failed_pydantic, (
            f"Expected schema {schema_name} invalid case #{idx+1} to fail validation, but it passed!"
        )
