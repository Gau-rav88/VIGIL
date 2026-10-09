from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import os
import signal

import websockets
from aiokafka import AIOKafkaProducer
from vigil_common.logging import get_logger, setup_logging

logger = get_logger("social_ingest")


class SocialIngester:
    def __init__(self) -> None:
        self.ws_url = os.getenv("SOCIAL_WS_URL", "ws://simulator:8090/ws/social")
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.pepper = os.getenv("PSEUDONYM_PEPPER", "change-me-dev-pepper-32bytes-min").encode("utf-8")
        self.keep_scenario_labels = os.getenv("KEEP_SCENARIO_LABELS", "false").lower() == "true"
        self.producer: AIOKafkaProducer | None = None
        self.running = False
        self.stats = {"messages": 0, "errors": 0}

    def _pseudonymize(self, raw_author: str) -> str:
        h = hmac.new(self.pepper, raw_author.encode("utf-8"), hashlib.sha256).hexdigest()
        return h[:22]

    async def start(self) -> None:
        self.running = True
        logger.info(
            "Starting social_ingest",
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
        logger.info("Kafka producer connected for social messages")

        reconnect_delay = 1.0
        while self.running:
            try:
                logger.info("Connecting to social simulator WebSocket...", url=self.ws_url)
                async with websockets.connect(self.ws_url, max_size=10 * 1024 * 1024) as ws:
                    reconnect_delay = 1.0
                    logger.info("Connected to social simulator stream")
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
                logger.error("Unexpected error in social ingest loop", error=str(exc))
                await asyncio.sleep(1.0)

    async def _process_message(self, raw_msg: str | bytes) -> None:
        try:
            data = json.loads(raw_msg)
            # Pseudonymize author
            if "author_id" in data:
                data["author_id"] = self._pseudonymize(data["author_id"])

            # Append ingest timestamp
            data["ts_ingest"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Strip scenario label if not in test mode
            if not self.keep_scenario_labels:
                data.pop("scenario_label", None)

            channel_id = data.get("channel_id", "ch-default")
            key = channel_id.encode("utf-8")
            payload = json.dumps(data).encode("utf-8")

            if self.producer:
                await self.producer.send(
                    topic="social.messages.raw",
                    value=payload,
                    key=key,
                )
            self.stats["messages"] += 1

            if self.stats["messages"] % 100 == 0:
                logger.info("Social ingest progress", **self.stats)

        except Exception as exc:
            self.stats["errors"] += 1
            logger.error("Failed to process social message", error=str(exc))

    async def stop(self) -> None:
        self.running = False
        if self.producer:
            await self.producer.stop()
        logger.info("Social ingester stopped cleanly")


async def run() -> None:
    setup_logging()
    ingester = SocialIngester()

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
