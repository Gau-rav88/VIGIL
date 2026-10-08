from __future__ import annotations

import asyncio
import collections
import datetime
import json
import os
import signal
from typing import Any
import websockets
from aiokafka import AIOKafkaProducer

from vigil_common.logging import get_logger, setup_logging

logger = get_logger("market_ingest")


class MarketIngester:
    def __init__(self) -> None:
        self.ws_url = os.getenv("MARKET_WS_URL", "ws://simulator:8090/ws/market")
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.keep_scenario_labels = os.getenv("KEEP_SCENARIO_LABELS", "false").lower() == "true"
        self.producer: AIOKafkaProducer | None = None
        self.running = False
        self.seen_events: collections.deque[str] = collections.deque(maxlen=100000)
        self.seen_set: set[str] = set()
        self.stats = {"trades": 0, "l2": 0, "l3": 0, "dupes": 0, "errors": 0}

    def _is_duplicate(self, event_id: str) -> bool:
        if event_id in self.seen_set:
            return True
        if len(self.seen_events) >= 100000:
            oldest = self.seen_events.popleft()
            self.seen_set.discard(oldest)
        self.seen_events.append(event_id)
        self.seen_set.add(event_id)
        return False

    async def start(self) -> None:
        self.running = True
        logger.info(
            "Starting market_ingest",
            ws_url=self.ws_url,
            kafka_bootstrap=self.kafka_bootstrap,
            keep_scenario_labels=self.keep_scenario_labels,
        )

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            acks=1,
            linger_ms=5,
        )
        await self.producer.start()
        logger.info("Kafka producer connected to Redpanda")

        reconnect_delay = 1.0
        while self.running:
            try:
                logger.info("Connecting to market simulator WebSocket...", url=self.ws_url)
                async with websockets.connect(self.ws_url, max_size=10 * 1024 * 1024) as ws:
                    reconnect_delay = 1.0
                    logger.info("Connected to market simulator stream")
                    while self.running:
                        msg = await ws.recv()
                        await self._process_message(msg)

            except (websockets.ConnectionClosed, OSError) as exc:
                if not self.running:
                    break
                logger.warning("WebSocket disconnected, retrying...", error=str(exc), delay=reconnect_delay)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 10.0)
            except Exception as exc:
                if not self.running:
                    break
                logger.error("Unexpected error in market ingest loop", error=str(exc))
                await asyncio.sleep(1.0)

    async def _process_message(self, raw_msg: str | bytes) -> None:
        try:
            frame = json.loads(raw_msg)
            kind = frame.get("kind")
            data = frame.get("data")
            if not kind or not data:
                return

            event_id = data.get("event_id")
            if event_id and self._is_duplicate(event_id):
                self.stats["dupes"] += 1
                return

            # Append ingest timestamp
            data["ts_ingest"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Strip scenario label if not in test mode
            if not self.keep_scenario_labels:
                data.pop("scenario_label", None)

            symbol = data.get("symbol", "UNKNOWN")
            key = symbol.encode("utf-8")
            payload = json.dumps(data).encode("utf-8")

            if kind == "trade":
                topic = "market.trades.norm"
                self.stats["trades"] += 1
            elif kind == "l2":
                topic = "market.l2.norm"
                self.stats["l2"] += 1
            elif kind == "l3":
                topic = "market.l3.norm"
                self.stats["l3"] += 1
            else:
                return

            if self.producer:
                await self.producer.send(topic=topic, value=payload, key=key)

            total = sum(self.stats.values())
            if total > 0 and total % 5000 == 0:
                logger.info("Market ingest progress", **self.stats)

        except Exception as exc:
            self.stats["errors"] += 1
            logger.error("Failed to process market message", error=str(exc))

    async def stop(self) -> None:
        self.running = False
        if self.producer:
            await self.producer.stop()
        logger.info("Market ingester stopped cleanly")


async def run() -> None:
    setup_logging()
    ingester = MarketIngester()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(ingester.start())

    await stop_event.wait()
    await ingester.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
