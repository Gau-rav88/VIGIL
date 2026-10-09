from __future__ import annotations

import asyncio
import collections
import datetime
import hashlib
import json
import os
import re
import signal
import uuid
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from vigil_common.logging import get_logger, setup_logging
from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef
from vigil_common.models.social import ParserMetadata, SocialSignal

logger = get_logger("social_intel")

BUY_CALL_PATTERNS = [
    r"\bbuy now\b", r"\bstrong buy\b", r"\bload up\b", r"\baccumulate\b",
    r"\bmultibagger\b", r"\brocket\b", r"\bkharido\b", r"\blelo\b", r"\bpump\b"
]
HOLD_PATTERNS = [r"\bhold tight\b", r"\bdon'?t sell\b", r"\bhold karo\b", r"\bbechna mat\b"]
EXIT_PATTERNS = [r"\bdump\b", r"\bexit now\b", r"\bbook profit\b", r"\bbecho\b", r"\bniklo\b"]
TIMING_PATTERNS = [r"\bsharp at\b", r"\bcoordinate\b", r"\bsab milke\b", r"\bat \d\d:\d\d\b"]
URGENCY_PATTERNS = [r"\burgent\b", r"\bhurry\b", r"\blast chance\b", r"\bbreaking\b", r"\bjaldi\b"]


class SocialIntelDetector:
    def __init__(self) -> None:
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.running = False

        # Ticker -> deque of recent signals (ts, author_id, cta, is_dup, urgency, channel_id, msg_id)
        self.ticker_windows: dict[str, collections.deque[dict[str, Any]]] = (
            collections.defaultdict(lambda: collections.deque(maxlen=2000))
        )
        self.recent_hashes: collections.deque[str] = collections.deque(maxlen=1000)
        self.cooldowns: dict[str, float] = {}
        self.config_hash = hashlib.sha256(b"social_intel_detectors_v1").hexdigest()

    async def start(self) -> None:
        self.running = True
        logger.info("Starting social_intel agent...", bootstrap=self.kafka_bootstrap)

        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            "social.messages.raw",
            bootstrap_servers=self.kafka_bootstrap,
            group_id="social_intel_workers",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Connected to social.messages.raw")

        async for record in self.consumer:
            if not self.running:
                break
            try:
                data = json.loads(record.value)
                await self._process_message(data)
            except Exception as exc:
                logger.error("Error processing social message in social_intel", error=str(exc))

    async def _process_message(self, msg: dict[str, Any]) -> None:
        text = msg.get("text", "")
        author_id = msg.get("author_id", "")
        channel_id = msg.get("channel_id", "")
        msg_id = msg.get("message_id", "")
        raw_hash = msg.get("raw_sha256", hashlib.sha256(text.encode("utf-8")).hexdigest())
        platform = msg.get("platform", "telegram")
        ts_posted = msg.get("ts_posted", datetime.datetime.now(datetime.timezone.utc).isoformat())

        # Extract tickers: e.g. $ZENITHSME or uppercase tokens
        tickers = re.findall(r"\$([A-Z0-9&._-]+)", text)
        if not tickers:
            tickers = re.findall(r"\b(ZENITHSME|RELIANCE|TCS|INFY|ACMESYSTEMS|NOVAPHARMA|SOLARIS)\b", text)

        if not tickers:
            return

        ticker = tickers[0]
        text_lower = text.lower()

        # Classify CTA
        cta_class = "NEUTRAL"
        if any(re.search(p, text_lower) for p in BUY_CALL_PATTERNS):
            cta_class = "BUY_CALL"
        elif any(re.search(p, text_lower) for p in HOLD_PATTERNS):
            cta_class = "HOLD_PUMP"
        elif any(re.search(p, text_lower) for p in EXIT_PATTERNS):
            cta_class = "EXIT_SIGNAL"
        elif any(re.search(p, text_lower) for p in TIMING_PATTERNS):
            cta_class = "COORDINATION_TIMING"

        # Check urgency
        urgency = 0.8 if any(re.search(p, text_lower) for p in URGENCY_PATTERNS) else 0.2

        # Check target price
        target_match = re.search(r"target\s*(\d+(\.\d+)?)", text_lower)
        target_price = target_match.group(1) if target_match else None

        # Check duplicate
        is_dup = raw_hash in self.recent_hashes
        self.recent_hashes.append(raw_hash)

        # Build SocialSignal
        sig = SocialSignal(
            schema_version="1.0.0",
            signal_id=str(uuid.uuid4()),
            message_event_id=msg.get("event_id", str(uuid.uuid4())),
            platform=platform,
            channel_id=channel_id,
            author_id=author_id,
            ts_posted=ts_posted,
            ts_processed=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ticker=ticker,
            ticker_confidence=0.95,
            mention_type="CASHTAG" if f"${ticker}" in text else "SYMBOL",
            cta_class=cta_class,  # type: ignore[arg-type]
            cta_confidence=0.90,
            target_price=target_price,
            urgency=urgency,
            sentiment=0.8 if cta_class in ("BUY_CALL", "HOLD_PUMP") else 0.0,
            raw_sha256=raw_hash,
            parser=ParserMetadata(mode="FALLBACK_RULES", version="1.0.0"),
        )

        # Publish SocialSignal to social.signals.norm
        if self.producer:
            await self.producer.send(
                topic="social.signals.norm",
                value=json.dumps(sig.model_dump()).encode("utf-8"),
                key=ticker.encode("utf-8"),
            )

        # Buffer for Hype Score calculation
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        win = self.ticker_windows[ticker]
        win.append({
            "ts": now_ts,
            "author_id": author_id,
            "cta_class": cta_class,
            "is_dup": is_dup,
            "urgency": urgency,
            "channel_id": channel_id,
            "message_id": msg_id,
        })

        await self._check_hype_burst(ticker)

    async def _check_hype_burst(self, ticker: str) -> None:
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        win = self.ticker_windows[ticker]

        # 60s sliding window
        cutoff = now_ts - 60.0
        recent = [s for s in win if s["ts"] >= cutoff]
        if len(recent) < 5:
            return

        # Feature factors
        # 1. f_rate: message arrival rate normalized (e.g. 10 msgs in window = 1.0)
        f_rate = min(1.0, len(recent) / 10.0)
        # 2. f_auth: unique author concentration (low unique authors = higher synthetic score)
        unique_authors = len({s["author_id"] for s in recent})
        f_auth = max(0.0, 1.0 - (unique_authors / len(recent)))
        # 3. f_cta: buy call ratio
        buy_calls = sum(1 for s in recent if s["cta_class"] in ("BUY_CALL", "HOLD_PUMP"))
        f_cta = buy_calls / len(recent)
        # 4. f_dup: duplicate text ratio
        f_dup = sum(1 for s in recent if s["is_dup"]) / len(recent)
        # 5. f_urg: urgency average
        f_urg = sum(s["urgency"] for s in recent) / len(recent)
        # 6. f_xch: multi-channel cross-posting
        unique_channels = len({s["channel_id"] for s in recent})
        f_xch = min(1.0, unique_channels / 3.0)

        # Hype Score formula:
        hype_score = 100.0 * (
            0.25 * f_rate
            + 0.15 * f_auth
            + 0.20 * f_cta
            + 0.15 * f_dup
            + 0.10 * f_urg
            + 0.15 * f_xch
        )

        logger.info("Evaluating hype score", ticker=ticker, score=round(hype_score, 1), count=len(recent))

        if hype_score >= 70.0:
            cooldown = self.cooldowns.get(ticker, 0.0)
            if (now_ts - cooldown) < 15.0:
                return
            self.cooldowns[ticker] = now_ts

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            start_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)).isoformat()

            evidence = [
                EvidenceRef(kind="social_message_id", ref=s["message_id"])
                for s in recent[:10] if s["message_id"]
            ] or [EvidenceRef(kind="social_message_id", ref="M-00000001")]

            anom = AnomalyEvent(
                schema_version="1.0.0",
                anomaly_id=str(uuid.uuid4()),
                type="HYPE_BURST",
                source_agent="social_intel",
                symbol=ticker,
                window_start=start_iso,
                window_end=now_iso,
                score=min(1.0, hype_score / 100.0),
                severity="HIGH" if hype_score >= 85.0 else "MEDIUM",
                metrics={
                    "hype_score": round(hype_score, 2),
                    "f_rate": round(f_rate, 2),
                    "f_cta": round(f_cta, 2),
                    "f_dup": round(f_dup, 2),
                    "messages_in_window": len(recent),
                },
                participants=list({s["author_id"] for s in recent})[:10],
                evidence_refs=evidence,
                detector_version="1.0.0",
                config_hash=self.config_hash,
                detected_at=now_iso,
            )

            logger.info("Detected social hype burst", ticker=ticker, score=hype_score)
            if self.producer:
                await self.producer.send(
                    topic="anomaly.social",
                    value=json.dumps(anom.model_dump()).encode("utf-8"),
                    key=ticker.encode("utf-8"),
                )

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Social intel detector stopped cleanly")


async def run() -> None:
    setup_logging()
    detector = SocialIntelDetector()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(detector.start())

    await stop_event.wait()
    await detector.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
