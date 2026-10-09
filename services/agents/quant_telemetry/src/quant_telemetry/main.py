from __future__ import annotations

import asyncio
import json
import os
import signal

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from vigil_common.logging import get_logger, setup_logging
from vigil_common.models.anomaly import AnomalyEvent

from .engine import QuantTelemetryEngine

logger = get_logger("quant_telemetry")


class QuantTelemetryService:
    def __init__(self) -> None:
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.engine = QuantTelemetryEngine()
        self.running = False

    async def start(self) -> None:
        self.running = True
        logger.info("Starting quant_telemetry service...", bootstrap=self.kafka_bootstrap)

        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        topics = ["market.trades.norm", "market.l2.norm", "market.l3.norm"]
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.kafka_bootstrap,
            group_id="quant_telemetry_workers",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Subscribed to market topics", topics=topics)

        async for record in self.consumer:
            if not self.running:
                break
            try:
                data = json.loads(record.value)
                event_type = "trade"
                if record.topic == "market.l2.norm":
                    event_type = "l2"
                elif record.topic == "market.l3.norm":
                    event_type = "l3"

                anomalies = self.engine.process_event(event_type, data)
                for anom in anomalies:
                    await self._emit_anomaly(anom)
            except Exception as exc:
                logger.error("Error processing market record in quant_telemetry", error=str(exc))

    async def _emit_anomaly(self, anomaly: AnomalyEvent) -> None:
        logger.info(
            "Detected market anomaly",
            type=anomaly.type,
            symbol=anomaly.symbol,
            score=anomaly.score,
            severity=anomaly.severity,
        )
        if self.producer:
            await self.producer.send(
                topic="anomaly.market",
                value=json.dumps(anomaly.model_dump(mode="json")).encode("utf-8"),
                key=anomaly.symbol.encode("utf-8"),
            )

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Quant telemetry service stopped cleanly")


async def run() -> None:
    setup_logging()
    svc = QuantTelemetryService()

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
