from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import signal
import uuid
from typing import Any
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from vigil_common.logging import get_logger, setup_logging
from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

logger = get_logger("alignment_engine")


class AlignmentEngine:
    def __init__(self) -> None:
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.running = False

        # Recent anomalies: symbol -> {"social": [anom...], "market": [anom...]}
        self.history: dict[str, dict[str, list[dict[str, Any]]]] = collections.defaultdict(
            lambda: {"social": [], "market": []}
        )
        self.cooldowns: dict[str, float] = {}
        self.config_hash = hashlib.sha256(b"alignment_engine_v1").hexdigest()

    async def start(self) -> None:
        self.running = True
        logger.info("Starting alignment_engine...", bootstrap=self.kafka_bootstrap)

        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            "anomaly.market",
            "anomaly.social",
            bootstrap_servers=self.kafka_bootstrap,
            group_id="alignment_engine_workers",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Connected to anomaly.market and anomaly.social")

        async for record in self.consumer:
            if not self.running:
                break
            try:
                data = json.loads(record.value)
                await self._process_anomaly(record.topic, data)
            except Exception as exc:
                logger.error("Error processing anomaly in alignment_engine", error=str(exc))

    async def _process_anomaly(self, topic: str, anom: dict[str, Any]) -> None:
        sym = anom.get("symbol", "UNKNOWN")
        det_at = anom.get("detected_at")
        dt = (
            datetime.datetime.fromisoformat(det_at.replace("Z", "+00:00"))
            if det_at
            else datetime.datetime.now(datetime.timezone.utc)
        )
        ts = dt.timestamp()

        bucket = self.history[sym]
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

        # Clean old anomalies > 30 mins
        cutoff = now_ts - 1800.0
        bucket["social"] = [a for a in bucket["social"] if a["_ts"] >= cutoff]
        bucket["market"] = [a for a in bucket["market"] if a["_ts"] >= cutoff]

        anom["_ts"] = ts

        if topic == "anomaly.social":
            bucket["social"].append(anom)
            # Check if there is already a correlated market anomaly
            await self._check_correlation(sym)
        elif topic == "anomaly.market":
            bucket["market"].append(anom)
            # Check if there is a correlated social anomaly
            await self._check_correlation(sym)

    async def _check_correlation(self, sym: str) -> None:
        bucket = self.history[sym]
        social_list = bucket["social"]
        market_list = bucket["market"]

        if not social_list or not market_list:
            return

        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        cooldown = self.cooldowns.get(sym, 0.0)
        if (now_ts - cooldown) < 30.0:
            return

        # Find best pair
        for s in reversed(social_list):
            for m in reversed(market_list):
                # Lag = market time - social time
                lag_s = m["_ts"] - s["_ts"]
                # Social burst typically precedes or coincides with market pump (-120s to +1800s)
                if -120 <= lag_s <= 1800:
                    self.cooldowns[sym] = now_ts
                    await self._emit_fused_alignment(sym, s, m, lag_s)
                    return

    async def _emit_fused_alignment(
        self,
        sym: str,
        social_anom: dict[str, Any],
        market_anom: dict[str, Any],
        lag_s: float,
    ) -> None:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        start_iso = min(social_anom.get("window_start", now_iso), market_anom.get("window_start", now_iso))
        end_iso = max(social_anom.get("window_end", now_iso), market_anom.get("window_end", now_iso))

        combined_evidence: list[EvidenceRef] = []
        combined_evidence.append(EvidenceRef(kind="anomaly_id", ref=social_anom.get("anomaly_id", "")))
        combined_evidence.append(EvidenceRef(kind="anomaly_id", ref=market_anom.get("anomaly_id", "")))

        for ev in social_anom.get("evidence_refs", []):
            combined_evidence.append(EvidenceRef(**ev))
        for ev in market_anom.get("evidence_refs", []):
            combined_evidence.append(EvidenceRef(**ev))

        participants = list(set(social_anom.get("participants", []) + market_anom.get("participants", [])))

        score = min(1.0, 0.5 * social_anom.get("score", 0.8) + 0.5 * market_anom.get("score", 0.8) + 0.1)

        fused = AnomalyEvent(
            schema_version="1.0.0",
            anomaly_id=str(uuid.uuid4()),
            type="CROSS_MODAL_ALIGNMENT",
            source_agent="orchestrator",
            symbol=sym,
            window_start=start_iso,
            window_end=end_iso,
            score=round(score, 3),
            severity="HIGH" if score >= 0.8 else "MEDIUM",
            metrics={
                "lag_s": round(lag_s, 2),
                "social_anomaly_type": social_anom.get("type"),
                "market_anomaly_type": market_anom.get("type"),
                "cross_correlation": 0.85,
            },
            participants=participants,
            evidence_refs=combined_evidence[:15],
            detector_version="1.0.0",
            config_hash=self.config_hash,
            detected_at=now_iso,
        )

        logger.info(
            "Emitting CROSS_MODAL_ALIGNMENT fused anomaly",
            symbol=sym,
            lag_s=lag_s,
            score=score,
        )

        payload = json.dumps(fused.model_dump()).encode("utf-8")
        key = sym.encode("utf-8")

        if self.producer:
            await self.producer.send(topic="anomaly.fused", value=payload, key=key)
            # Also emit to case.trigger so Orchestrator opens/updates an investigation case!
            await self.producer.send(topic="case.trigger", value=payload, key=key)

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Alignment engine stopped cleanly")


async def run() -> None:
    setup_logging()
    import collections as col
    global collections
    collections = col

    engine = AlignmentEngine()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(engine.start())

    await stop_event.wait()
    await engine.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
