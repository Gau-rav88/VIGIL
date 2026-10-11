from __future__ import annotations

import asyncio
import json
import os
import signal
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from vigil_common.logging import get_logger, setup_logging
from vigil_common.models.anomaly import AnomalyEvent
from vigil_common.models.social import SocialSignal
from vigil_common.network import resolve_kafka_bootstrap
from vigil_common.topics import Topics

from social_intel.engine import SocialIntelEngine

logger = get_logger("social_intel")


class SocialIntelService:
    def __init__(self) -> None:
        self.kafka_bootstrap = resolve_kafka_bootstrap(os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092"))
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.engine = SocialIntelEngine()
        self.running = False
        self.stats = {"messages": 0, "signals": 0, "anomalies": 0}

    async def start(self) -> None:
        self.running = True
        logger.info("Starting social_intel service...", bootstrap=self.kafka_bootstrap)

        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            Topics.SOCIAL_MESSAGES_RAW,
            bootstrap_servers=self.kafka_bootstrap,
            group_id="social_intel_workers",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Subscribed to social.messages.raw")

        async for record in self.consumer:
            if not self.running:
                break
            try:
                data = json.loads(record.value)
                self.stats["messages"] += 1
                signals, anomalies, hype_records = await self.engine.process_message_async(data)

                for sig in signals:
                    await self._emit_signal(sig)

                for anom in anomalies:
                    await self._emit_anomaly(anom)

                for h in hype_records:
                    await self._emit_hype(h)

                if self.stats["messages"] % 100 == 0:
                    logger.info("Social intel progress", **self.stats)

            except Exception as exc:
                logger.error("Error in social_intel processing", error=str(exc))

    async def _emit_signal(self, sig: SocialSignal) -> None:
        self.stats["signals"] += 1
        if self.producer:
            await self.producer.send(
                topic=Topics.SOCIAL_SIGNALS_NORM,
                value=json.dumps(sig.model_dump(mode="json")).encode("utf-8"),
                key=sig.ticker.encode("utf-8"),
            )

    async def _emit_anomaly(self, anom: AnomalyEvent) -> None:
        self.stats["anomalies"] += 1
        logger.info(
            "Detected social anomaly",
            type=anom.type,
            symbol=anom.symbol,
            score=anom.score,
            severity=anom.severity,
        )
        if self.producer:
            await self.producer.send(
                topic=Topics.ANOMALY_SOCIAL,
                value=json.dumps(anom.model_dump(mode="json")).encode("utf-8"),
                key=anom.symbol.encode("utf-8"),
            )

    async def _emit_hype(self, hype: dict[str, Any]) -> None:
        if self.producer:
            ticker = hype.get("ticker", "UNKNOWN")
            await self.producer.send(
                topic=Topics.HYPE_SCORES_NORM,
                value=json.dumps(hype).encode("utf-8"),
                key=ticker.encode("utf-8"),
            )

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Social intel service stopped cleanly", **self.stats)


async def run() -> None:
    setup_logging()
    svc = SocialIntelService()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(svc.start())

    await stop_event.wait()
    await svc.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
