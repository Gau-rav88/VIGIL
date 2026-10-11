from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from alignment_engine.main import AlignmentEngine


@pytest.mark.asyncio
async def test_fast_path_insufficient_series_emits_candidate_only() -> None:
    engine = AlignmentEngine()
    engine.producer = AsyncMock()
    engine.producer.send = AsyncMock()
    engine.producer.send_and_wait = AsyncMock()
    engine.producer.flush = AsyncMock()

    # Short / empty series
    h = np.zeros(3600, dtype=np.float64)
    v = np.zeros(3600, dtype=np.float64)
    # Only 5 non-zero observations (< ALIGN_MIN_OBS = 30)
    h[:5] = [10.0, 20.0, 30.0, 40.0, 50.0]
    v[:5] = [1.0, 2.0, 3.0, 4.0, 5.0]

    with patch("alignment_engine.main.fetch_series", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (h, v, np.zeros(3600), np.zeros(3600), False)
        engine.db_pool = MagicMock()
        mock_conn = AsyncMock()
        engine.db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        engine.db_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        burst = {"type": "HYPE_BURST", "_ts": 1000.0, "score": 0.9, "participants": ["ch_1"]}
        mev = {"type": "VOLUME_SPIKE", "_ts": 1150.0, "score": 0.85, "participants": ["acc_1"]}
        engine.history["TEST_SYM"]["social"].append(burst)
        engine.history["TEST_SYM"]["market"].append(mev)

        await engine._check_fast_path("TEST_SYM", 1200.0)

        # Assert producer sent ALIGNMENT_CANDIDATE to anomaly.fused and NOT to case.trigger
        assert engine.producer.send.called
        call_args = engine.producer.send.call_args
        topic = call_args[1]["topic"]
        assert topic == "anomaly.fused"
        payload_bytes = call_args[1]["value"]
        assert b"ALIGNMENT_CANDIDATE" in payload_bytes
        assert b"statistical_test" in payload_bytes
        assert b"not_run" in payload_bytes
        assert b"xcorr_peak" not in payload_bytes


@pytest.mark.asyncio
async def test_fast_path_strong_lead_emits_cross_modal_alignment() -> None:
    engine = AlignmentEngine()
    engine.producer = AsyncMock()
    engine.producer.send = AsyncMock()
    engine.producer.flush = AsyncMock()

    # Create synthetic series with strong correlation: lag=120s
    n = 3600
    t = np.arange(n, dtype=float)
    h = 80.0 * np.exp(-0.5 * ((t - 500) / 40) ** 2)
    v = 5.0 * np.exp(-0.5 * ((t - (500 + 120)) / 40) ** 2)

    with patch("alignment_engine.main.fetch_series", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (h, v, np.zeros(n), np.zeros(n), True)
        engine.db_pool = MagicMock()
        mock_conn = AsyncMock()
        engine.db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        engine.db_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        burst = {"type": "HYPE_BURST", "_ts": 1000.0, "score": 0.95, "participants": ["tg_lead"]}
        mev = {"type": "VOLUME_SPIKE", "_ts": 1120.0, "score": 0.90, "participants": ["acc_buyer"]}
        engine.history["TARGET_SYM"]["social"].append(burst)
        engine.history["TARGET_SYM"]["market"].append(mev)

        await engine._check_fast_path("TARGET_SYM", 1150.0)

        # Assert producer sent CROSS_MODAL_ALIGNMENT to both anomaly.fused and case.trigger
        sent_topics = [call[1]["topic"] for call in engine.producer.send.call_args_list]
        assert "anomaly.fused" in sent_topics
        assert "case.trigger" in sent_topics


@pytest.mark.asyncio
async def test_fast_path_noise_emits_candidate_only() -> None:
    engine = AlignmentEngine()
    engine.producer = AsyncMock()
    engine.producer.send = AsyncMock()
    engine.producer.send_and_wait = AsyncMock()
    engine.producer.flush = AsyncMock()

    # Uncorrelated noise
    rng = np.random.default_rng(999)
    n = 3600
    h = rng.uniform(0, 10, n)
    v = rng.uniform(0, 5, n)

    with patch("alignment_engine.main.fetch_series", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (h, v, np.zeros(n), np.zeros(n), True)
        engine.db_pool = MagicMock()
        mock_conn = AsyncMock()
        engine.db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        engine.db_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        burst = {"type": "HYPE_BURST", "_ts": 1000.0, "score": 0.8, "participants": ["social_user"]}
        mev = {"type": "PRICE_JUMP", "_ts": 1050.0, "score": 0.8, "participants": ["market_user"]}
        engine.history["NOISE_SYM"]["social"].append(burst)
        engine.history["NOISE_SYM"]["market"].append(mev)

        await engine._check_fast_path("NOISE_SYM", 1100.0)

        # Uncorrelated noise should fail significance (p >= P_THRESHOLD or low peak) -> candidate only
        assert engine.producer.send.called
        call_args = engine.producer.send.call_args
        assert call_args[1]["topic"] == "anomaly.fused"
        payload_bytes = call_args[1]["value"]
        assert b"ALIGNMENT_CANDIDATE" in payload_bytes
