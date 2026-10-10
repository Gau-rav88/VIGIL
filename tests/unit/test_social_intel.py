from __future__ import annotations

import datetime

import pytest
from social_intel.cta_classifier import CtaClassifier
from social_intel.engine import SocialIntelEngine
from social_intel.hype_scorer import HypeScorer, sigmoid
from social_intel.near_dup import MinHashLSH
from social_intel.normalization import emoji_density, extract_emojis, normalize_text
from social_intel.ticker_extractor import TickerExtractor


def test_normalization_and_emojis() -> None:
    raw = "  Check out $ZENITHSME at https://spam.com/link @user_123 🚀🚀 rocket!  "
    norm = normalize_text(raw)
    assert "$ZENITHSME" in norm
    assert "https://" not in norm
    assert "@user_123" not in norm
    assert "rocket!" in norm

    emojis = extract_emojis("Huge pump incoming! 🚀📈🔥")
    assert "🚀" in emojis
    assert "📈" in emojis
    assert "🔥" in emojis
    assert emoji_density("🚀📈🔥") > 0.5
    assert emoji_density("") == 0.0
    assert normalize_text("") == ""


def test_ticker_extractor_cashtags_aliases_ambiguity() -> None:
    extractor = TickerExtractor()

    # 1. Cashtag
    res1 = extractor.extract_tickers("Strong breakout on $ZENITHSME today")
    assert len(res1) == 1
    assert res1[0][0] == "ZENITHSME"
    assert res1[0][1] == 0.95
    assert res1[0][2] == "CASHTAG"

    # 2. Company Name
    res2 = extractor.extract_tickers("Board meeting at Zenith SME Technologies Ltd tomorrow")
    assert len(res2) == 1
    assert res2[0][0] == "ZENITHSME"
    assert res2[0][2] == "COMPANY_NAME"

    # 3. Standard Symbol
    res3 = extractor.extract_tickers("Looking at quarterly results for RELIANCE and TCS")
    syms = {r[0] for r in res3}
    assert "RELIANCE" in syms
    assert "TCS" in syms

    # 4. Ambiguous token WITH financial cue
    res4 = extractor.extract_tickers("Huge breakout rally on ZEN stock today")
    assert len(res4) == 1
    assert res4[0][0] == "ZENITHSME"

    # 5. Ambiguous token WITHOUT financial cue (should not match)
    res5 = extractor.extract_tickers("Finding inner peace through zen meditation")
    assert len(res5) == 0

    # 6. Another ambiguous token SOLAR with cue
    res6 = extractor.extract_tickers("Strong buy on SOLAR shares at CMP")
    assert len(res6) == 1
    assert res6[0][0] == "SOLARIS"


def test_cta_classifier_fallback() -> None:
    classifier = CtaClassifier()

    # BUY_CALL
    b = classifier.classify_fallback("Everyone buy now before upper circuit!")
    assert b["cta_class"] == "BUY_CALL"
    assert b["cta_confidence"] >= 0.7
    assert b["sentiment"] > 0

    # Hinglish BUY_CALL
    b_hi = classifier.classify_fallback("Kharido daba ke, multibagger banega!")
    assert b_hi["cta_class"] == "BUY_CALL"

    # HOLD_PUMP
    h = classifier.classify_fallback("Hold tight and don't sell diamond hands!")
    assert h["cta_class"] == "HOLD_PUMP"

    # Hinglish HOLD_PUMP
    h_hi = classifier.classify_fallback("Bechna mat ek bhi share, hold karo!")
    assert h_hi["cta_class"] == "HOLD_PUMP"

    # EXIT_SIGNAL
    e = classifier.classify_fallback("Dump all shares immediately, exit now!")
    assert e["cta_class"] == "EXIT_SIGNAL"
    assert e["sentiment"] < 0

    # Hinglish EXIT_SIGNAL
    e_hi = classifier.classify_fallback("Niklo sabhi turant, operator dump chalu!")
    assert e_hi["cta_class"] == "EXIT_SIGNAL"

    # COORDINATION_TIMING
    t = classifier.classify_fallback("Place orders sharp at 14:30! Coordinated push!")
    assert t["cta_class"] == "COORDINATION_TIMING"
    assert t["scheduled_action_time"] is not None

    # TARGET_PRICE
    tp = classifier.classify_fallback("Big move target 65.50 incoming!")
    assert tp["target_price"] == "65.50"

    # NEUTRAL
    n = classifier.classify_fallback("Discussion on general macroeconomic inflation indices.")
    assert n["cta_class"] == "NEUTRAL"
    assert n["urgency"] <= 0.3


def test_near_duplicate_minhash_lsh() -> None:
    lsh = MinHashLSH(threshold=0.8, sliding_window_s=300.0)
    base_ts = 1000.0

    # Insert message 1
    t1 = "Bhai log $ZENITHSME me circuit lagne wala hai! 100% multibagger guaranteed!"
    cl1, sz1 = lsh.insert_and_cluster("msg1", t1, "auth1", "ch1", ts=base_ts)
    assert cl1 is not None
    assert sz1 == 1

    # Insert near duplicate message 2 (minor variation)
    t2 = "Bhai log $ZENITHSME me circuit lagne wala hai! 100% multibagger guaranteed, buy now!"
    cl2, sz2 = lsh.insert_and_cluster("msg2", t2, "auth2", "ch2", ts=base_ts + 5.0)
    assert cl2 == cl1
    assert sz2 == 2

    # Insert completely different message
    t3 = "Quarterly results of TCS showed 5% margin increase."
    cl3, sz3 = lsh.insert_and_cluster("msg3", t3, "auth3", "ch1", ts=base_ts + 10.0)
    assert cl3 != cl1
    assert sz3 == 1

    stats = lsh.get_cluster_stats(cl1)
    assert stats is not None
    assert stats["count"] == 2
    assert stats["unique_authors"] == 2
    assert stats["unique_channels"] == 2

    # Purge test: advance time beyond sliding window
    lsh.purge_expired(base_ts + 500.0)
    assert "msg1" not in lsh.records
    assert "msg2" not in lsh.records


def test_hype_scorer_math_and_burst() -> None:
    scorer = HypeScorer()
    now = 1000.0

    # 1. Sigmoid checks
    assert abs(sigmoid(0.0) - 0.5) < 1e-4
    assert sigmoid(10.0) > 0.99
    assert sigmoid(-10.0) < 0.01

    # 2. Small sample cap test: N < 5 caps hype_score <= 20.0
    for i in range(3):
        scorer.add_signal({
            "ticker": "ZENITHSME",
            "ticker_confidence": 0.95,
            "cta_class": "BUY_CALL",
            "cta_confidence": 0.9,
            "urgency": 0.9,
            "channel_id": f"ch_{i}",
            "author_id": f"auth_{i}",
            "ts_numeric": now - (3 - i),
        })

    metrics, anoms = scorer.evaluate_step("ZENITHSME", now_ts=now)
    assert metrics["msg_count"] == 3
    assert metrics["hype_score"] <= 20.0  # Invariant: small sample cap
    assert len(anoms) == 0

    # 3. Burst Generation: add continuous pump messages across channels (2 msgs/sec)
    for sec in range(50):
        for sub in range(2):
            scorer.add_signal({
                "ticker": "ZENITHSME",
                "ticker_confidence": 0.95,
                "cta_class": "BUY_CALL",
                "cta_confidence": 0.95,
                "urgency": 0.9,
                "near_dup_cluster_size": 4,
                "channel_id": f"ch_{sub % 3}",
                "author_id": f"pump_auth_{sec % 4}",
                "message_id": f"M-{sec:04d}-{sub}",
                "ts_numeric": now + sec + (sub * 0.4),
            })

    # Step forward 35s under sustained hype
    burst_detected = False
    for step in range(8):
        step_now = now + 10.0 + (step * 5.0)
        m, step_anoms = scorer.evaluate_step("ZENITHSME", now_ts=step_now)
        for a in step_anoms:
            if a.type == "HYPE_BURST":
                burst_detected = True
                assert a.symbol == "ZENITHSME"
                assert a.score >= 0.7
                assert a.source_agent == "social_intel"
                assert "hype_score" in a.metrics

    assert burst_detected, "HYPE_BURST should fire when hype >= 70 sustained for >= 30s"


def test_near_duplicate_campaign_anomaly() -> None:
    scorer = HypeScorer()
    stats = {
        "count": 6,
        "unique_authors": 4,
        "unique_channels": 3,
        "duration_s": 120.0,
    }
    anom = scorer.check_near_duplicate_campaign("cl_test_01", stats, "ZENITHSME", now_ts=2000.0)
    assert anom is not None
    assert anom.type == "NEAR_DUPLICATE_CAMPAIGN"
    assert anom.symbol == "ZENITHSME"
    assert anom.metrics["message_count"] == 6

    # Repeated check should return None (deduplicated)
    anom2 = scorer.check_near_duplicate_campaign("cl_test_01", stats, "ZENITHSME", now_ts=2005.0)
    assert anom2 is None


def test_social_intel_engine_end_to_end() -> None:
    engine = SocialIntelEngine()

    msg = {
        "event_id": "00000000-0000-0000-0000-000000000099",
        "platform": "telegram",
        "channel_id": "tg-pump-elite",
        "message_id": "M-00099",
        "author_id": "auth-operator",
        "text": "Bhai log $ZENITHSME upper circuit lagega! Buy now at CMP, target 60.00!",
        "ts_posted": "2026-10-10T12:00:00Z",
        "is_synthetic": True,
    }

    dt = datetime.datetime.fromisoformat("2026-10-10T12:00:00+00:00").timestamp()
    signals, anoms, hype = engine.process_message(msg, now_ts=dt)
    assert len(signals) == 1
    sig = signals[0]
    assert sig.ticker == "ZENITHSME"
    assert sig.cta_class in ("BUY_CALL", "TARGET_PRICE")
    assert sig.target_price == "60.00"

    # Test slice tool handler
    slice_data = engine.get_slice("ZENITHSME", "2026-10-10T11:00:00Z", "2026-10-10T13:00:00Z")
    assert slice_data["ticker"] == "ZENITHSME"
    assert slice_data["message_count"] >= 1
    assert "tg-pump-elite" in slice_data["channels"]


@pytest.mark.asyncio
async def test_social_intel_service_emitters_and_stop() -> None:
    from unittest.mock import AsyncMock

    from social_intel.main import SocialIntelService
    from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef
    from vigil_common.models.social import ParserMetadata, SocialSignal

    svc = SocialIntelService()
    mock_prod = AsyncMock()
    svc.producer = mock_prod

    sig = SocialSignal(
        schema_version="1.0.0",
        signal_id="00000000-0000-0000-0000-000000000001",
        message_event_id="00000000-0000-0000-0000-000000000002",
        platform="telegram",
        channel_id="ch-1",
        author_id="auth-001",
        ts_posted="2026-10-10T12:00:00Z",
        ticker="ZENITHSME",
        ticker_confidence=0.95,
        cta_class="BUY_CALL",
        urgency=0.9,
        raw_sha256="a" * 64,
        parser=ParserMetadata(mode="FALLBACK_RULES", version="1.0.0"),
    )
    await svc._emit_signal(sig)
    assert svc.stats["signals"] == 1
    assert mock_prod.send.call_count == 1

    anom = AnomalyEvent(
        schema_version="1.0.0",
        anomaly_id="00000000-0000-0000-0000-000000000003",
        type="HYPE_BURST",
        source_agent="social_intel",
        symbol="ZENITHSME",
        window_start="2026-10-10T11:59:00Z",
        window_end="2026-10-10T12:00:00Z",
        score=0.9,
        severity="HIGH",
        metrics={"hype_score": 85.0},
        evidence_refs=[EvidenceRef(kind="social_message_id", ref="M-01")],
        detector_version="1.0.0",
        config_hash="c" * 64,
        detected_at="2026-10-10T12:00:00Z",
    )
    await svc._emit_anomaly(anom)
    assert svc.stats["anomalies"] == 1

    await svc._emit_hype({"ticker": "ZENITHSME", "hype_score": 85.0})
    assert mock_prod.send.call_count == 3

    await svc.stop()
    assert not svc.running
