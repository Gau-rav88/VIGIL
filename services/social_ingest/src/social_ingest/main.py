from __future__ import annotations

import asyncio
import base64
import collections
import datetime
import hashlib
import json
import os
import signal
from typing import Any

import websockets
from aiokafka import AIOKafkaProducer
from vigil_common.logging import get_logger, setup_logging
from vigil_common.models.social import SocialMessage
from vigil_common.pseudonym import pseudonymize

logger = get_logger("social_ingest")


class SocialIngester:
    def __init__(self) -> None:
        self.ws_url = os.getenv("SOCIAL_WS_URL", "ws://simulator:8090/ws/social")
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.pepper = os.getenv("PSEUDONYM_PEPPER", "change-me-dev-pepper-32bytes-min")
        self.keep_scenario_labels = os.getenv("KEEP_SCENARIO_LABELS", "false").lower() == "true"
        self.producer: AIOKafkaProducer | None = None
        self.running = False
        self.stats = {"messages": 0, "errors": 0, "dlq": 0, "duplicates": 0}
        # LRU deduplication cache: (platform, channel_id, message_id) -> float
        self.dedupe_cache: collections.OrderedDict[tuple[str, str, str], float] = (
            collections.OrderedDict()
        )
        self.max_dedupe_entries = 100_000

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
                logger.warning(
                    "WebSocket disconnected, retrying...",
                    error=str(exc),
                    delay=reconnect_delay,
                )
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 10.0)
            except Exception as exc:
                if not self.running:
                    break
                logger.error("Unexpected error in social ingest loop", error=str(exc))
                await asyncio.sleep(1.0)

    async def _send_dlq(self, raw_bytes: bytes, reason: str, error: str) -> None:
        self.stats["dlq"] += 1
        dlq_record = {
            "stage": "social_ingest",
            "reason": reason,
            "error": error,
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "original_b64": base64.b64encode(raw_bytes).decode("ascii"),
        }
        if self.producer:
            await self.producer.send(
                topic="dlq.social",
                value=json.dumps(dlq_record).encode("utf-8"),
            )
        logger.warning("Routed social message to DLQ", reason=reason, error=error)

    async def _process_message(self, raw_msg: str | bytes) -> None:
        if isinstance(raw_msg, str):
            raw_bytes = raw_msg.encode("utf-8")
        else:
            raw_bytes = raw_msg

        try:
            data: dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:
            self.stats["errors"] += 1
            await self._send_dlq(
                raw_bytes,
                reason="INVALID_JSON",
                error=f"Malformed JSON: {exc}",
            )
            return

        # 1. Enforce Channel Visibility Gate (FR-SOC-08, P3-G1)
        channel_visibility = data.get("channel_visibility")
        if channel_visibility not in ("public", "lawful_access"):
            await self._send_dlq(
                raw_bytes,
                reason="VISIBILITY_NOT_PERMITTED",
                error=f"Channel visibility '{channel_visibility}' is not permitted. Only 'public' and 'lawful_access' allowed.",
            )
            return

        # 2. Extract platform and raw identifiers
        platform = data.get("platform", "telegram")
        raw_author = str(data.get("author_id", "unknown"))
        raw_msg_id = str(data.get("message_id", "0"))
        channel_id = str(data.get("channel_id", "default"))

        # Pseudonymize author_id (b64url of HMAC-SHA256[:16] -> 22 chars)
        pseudo_author = pseudonymize(raw_author, self.pepper, f"handle|{platform}")
        data["author_id"] = pseudo_author

        # Pseudonymize message_id (so raw message identifiers never leak into storage - P3-G3)
        pseudo_msg_id = pseudonymize(raw_msg_id, self.pepper, f"msg|{platform}")
        data["message_id"] = pseudo_msg_id

        # 3. Deduplication check on (platform, channel_id, message_id) (FR-SOC-07)
        now_epoch = datetime.datetime.now(datetime.timezone.utc).timestamp()
        dedupe_key = (platform, channel_id, pseudo_msg_id)
        if dedupe_key in self.dedupe_cache:
            last_seen = self.dedupe_cache[dedupe_key]
            if (now_epoch - last_seen) < 30.0:
                self.stats["duplicates"] += 1
                logger.debug("Dropped duplicate social message", dedupe_key=dedupe_key)
                return

        self.dedupe_cache[dedupe_key] = now_epoch
        if len(self.dedupe_cache) > self.max_dedupe_entries:
            self.dedupe_cache.popitem(last=False)

        # 4. Canonical raw JSON hash (FR-SOC-02)
        if not data.get("raw_sha256"):
            canonical_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
            data["raw_sha256"] = hashlib.sha256(canonical_bytes).hexdigest()

        # 5. Timestamping & scenario labels
        data["ts_ingest"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not self.keep_scenario_labels:
            data.pop("scenario_label", None)

        # 6. Validate against SocialMessage contract schema
        try:
            validated = SocialMessage.model_validate(data)
            validated_dict = validated.model_dump()
        except Exception as exc:
            self.stats["errors"] += 1
            await self._send_dlq(
                raw_bytes,
                reason="VALIDATION_ERROR",
                error=f"Schema validation failure: {exc}",
            )
            return

        # 7. Publish to social.messages.raw
        key = channel_id.encode("utf-8")
        payload = json.dumps(validated_dict).encode("utf-8")

        if self.producer:
            await self.producer.send(
                topic="social.messages.raw",
                value=payload,
                key=key,
            )
        self.stats["messages"] += 1

        if self.stats["messages"] % 100 == 0:
            logger.info("Social ingest progress", **self.stats)

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
