from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest
from social_intel.cta_classifier import CtaClassifier


@pytest.mark.asyncio
async def test_llm_timeout_bound_enforced() -> None:
    """
    Acceptance Criterion P3-G2:
    LLM calls honor timeout bound (LLM_TIMEOUT_S=2.0). Fault-injected call
    that exceeds timeout falls back gracefully to FALLBACK_RULES without hanging.
    """
    classifier = CtaClassifier()
    classifier.llm_timeout_s = 0.5  # Fast test timeout

    # Fault injection: mock API call sleeping longer than timeout
    async def slow_api_call(messages: list, api_key: str) -> list:
        await asyncio.sleep(2.0)
        return []

    with (
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test-key-mock"}),
        patch.object(classifier, "_call_llm_api", side_effect=slow_api_call),
    ):
        start = time.perf_counter()
        msgs = [{"message_id": "1", "text": "Buy $ZENITHSME now rocket!"}]
        results = await classifier.classify_with_llm(msgs)
        elapsed = time.perf_counter() - start

        # Must return within timeout tolerance (around 0.5s, well under 2.0s)
        assert elapsed < 1.0, f"Call did not timeout promptly: took {elapsed:.2f}s"
        assert len(results) == 1
        # Invariant: on timeout, graceful fallback occurs
        assert results[0]["parser_mode"] == "FALLBACK_RULES"
        assert results[0]["cta_class"] == "BUY_CALL"


@pytest.mark.asyncio
async def test_llm_concurrency_bound_enforced() -> None:
    """
    Acceptance Criterion P3-G2:
    LLM calls honor concurrency bounds (LLM_MAX_CONCURRENCY=8).
    Peak concurrent calls never exceed the semaphore bound.
    """
    classifier = CtaClassifier()
    classifier.llm_concurrency = 4
    classifier.semaphore = asyncio.Semaphore(4)
    classifier.llm_timeout_s = 5.0

    current_concurrent = 0
    peak_concurrent = 0
    lock = asyncio.Lock()

    async def tracked_api_call(messages: list, api_key: str) -> list:
        nonlocal current_concurrent, peak_concurrent
        async with lock:
            current_concurrent += 1
            if current_concurrent > peak_concurrent:
                peak_concurrent = current_concurrent
        await asyncio.sleep(0.05)
        async with lock:
            current_concurrent -= 1
        return [classifier.classify_fallback(m.get("text", "")) for m in messages]

    with (
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test-key-mock"}),
        patch.object(classifier, "_call_llm_api", side_effect=tracked_api_call),
    ):
        # Dispatch 16 concurrent requests
        tasks = [
            classifier.classify_with_llm([{"message_id": str(i), "text": f"Msg {i} $ZENITHSME buy"}])
            for i in range(16)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 16
        # Assert peak concurrency never exceeded the semaphore bound of 4
        assert peak_concurrent <= 4, f"Peak concurrency exceeded bound: {peak_concurrent} > 4"
        assert peak_concurrent >= 2, "Expected concurrent execution"
