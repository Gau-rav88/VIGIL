from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import signal
from typing import Any

import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from vigil_common.logging import get_logger, setup_logging

from attribution.engine import AttributionEngine
from attribution.graph_store import Neo4jGraphStore

logger = get_logger("attribution")


class AttributionService:
    def __init__(self) -> None:
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "vigilneo4j")
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

        self.store = Neo4jGraphStore(self.neo4j_uri, self.neo4j_user, self.neo4j_password)
        self.engine = AttributionEngine(self.store)

        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.redis_client: aioredis.Redis | None = None

        self.running = False
        self.trade_batch: list[dict[str, Any]] = []
        self.config_hash = hashlib.sha256(b"attribution_v1").hexdigest()
        self.watchlist_symbols: set[str] = {"ZENITHSME"}

    async def start(self) -> None:
        self.running = True
        logger.info("Starting Attribution Service...", neo4j=self.neo4j_uri)

        # 1. Connect Neo4j
        await self.store.connect()

        # 2. Connect Redis
        try:
            self.redis_client = aioredis.from_url(self.redis_url)
            logger.info("Connected to Redis")
        except Exception as exc:
            logger.warning("Could not connect to Redis", error=str(exc))

        # 3. Connect Kafka
        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            "market.trades.norm",
            bootstrap_servers=self.kafka_bootstrap,
            group_id="attribution_workers",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Connected to Kafka topic market.trades.norm")

        periodic_scan_task = asyncio.create_task(self._periodic_attribution_loop())
        periodic_flush_task = asyncio.create_task(self._periodic_flush_loop())

        try:
            async for record in self.consumer:
                if not self.running:
                    break
                try:
                    data = json.loads(record.value)
                    sym = data.get("symbol", "")
                    # Watchlist gate
                    if sym in self.watchlist_symbols:
                        trade_entry = {
                            "seller": data.get("seller", {}).get("account_id"),
                            "buyer": data.get("buyer", {}).get("account_id"),
                            "qty": data.get("qty", 0.0),
                            "price": data.get("price", 0.0),
                            "ts_ms": int(data.get("ts_exchange", 0)) if isinstance(data.get("ts_exchange"), int) else 0,
                            "trade_id": data.get("trade_id", ""),
                            "symbol": sym,
                            "seller_device_fp": data.get("seller", {}).get("device_fp"),
                            "buyer_device_fp": data.get("buyer", {}).get("device_fp"),
                            "seller_asn": data.get("seller", {}).get("asn"),
                            "buyer_asn": data.get("buyer", {}).get("asn"),
                            "seller_broker_id": data.get("seller", {}).get("broker_id"),
                            "buyer_broker_id": data.get("buyer", {}).get("broker_id"),
                            "seller_gateway_id": data.get("seller", {}).get("gateway_id"),
                            "buyer_gateway_id": data.get("buyer", {}).get("gateway_id"),
                        }
                        self.trade_batch.append(trade_entry)
                        if len(self.trade_batch) >= 100:
                            await self._flush_trades()
                except Exception as exc:
                    logger.error("Error processing trade record", error=str(exc))
        finally:
            periodic_scan_task.cancel()
            periodic_flush_task.cancel()
            await asyncio.gather(periodic_scan_task, periodic_flush_task, return_exceptions=True)

    async def _periodic_flush_loop(self) -> None:
        while self.running:
            await asyncio.sleep(2.0)
            await self._flush_trades()

    async def _flush_trades(self) -> None:
        if not self.trade_batch:
            return
        batch = self.trade_batch
        self.trade_batch = []
        try:
            await self.store.upsert_traders_and_trades(batch, symbol="ZENITHSME")
        except Exception as exc:
            logger.error("Failed to flush trade batch", error=str(exc))

    async def _periodic_attribution_loop(self) -> None:
        while self.running:
            await asyncio.sleep(10.0)
            await self._run_attribution_cycle()

    async def _run_attribution_cycle(self) -> None:
        # Refresh watchlist from Redis if available
        if self.redis_client:
            try:
                symbols = await self.redis_client.smembers("watchlist:symbols")
                if symbols:
                    self.watchlist_symbols.update(
                        s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in symbols
                    )
            except Exception as exc:
                logger.debug("Redis watchlist fetch failed", error=str(exc))

        for sym in list(self.watchlist_symbols):
            try:
                # Run attribution
                trades = list(self.store.fallback_nx.edges(data=True))
                formatted_trades = [
                    {
                        "seller": u,
                        "buyer": v,
                        "qty": d.get("qty", 0.0),
                        "price": d.get("price", 0.0),
                        "ts_ms": d.get("ts_ms", 0),
                        "trade_id": str(k),
                    }
                    for u, v, k, d in trades
                ]

                if not formatted_trades:
                    continue

                links, entities, cycles = self.engine.attribute_accounts(
                    trades=formatted_trades,
                    symbol=sym,
                    case_id=f"case_{sym.lower()}",
                )

                now_utc = datetime.datetime.now(datetime.timezone.utc)
                start_utc = now_utc - datetime.timedelta(seconds=600)
                now_iso = now_utc.isoformat()
                start_iso = start_utc.isoformat()

                # Generate anomaly events
                anomalies = self.engine.create_anomaly_events(
                    symbol=sym,
                    entities=entities,
                    cycles=cycles,
                    window_start_iso=start_iso,
                    window_end_iso=now_iso,
                    config_hash=self.config_hash,
                )

                if self.producer and anomalies:
                    for anom in anomalies:
                        payload = json.dumps(anom.model_dump()).encode("utf-8")
                        await self.producer.send(topic="anomaly.fused", value=payload, key=sym.encode("utf-8"))
                        await self.producer.send(topic="graph.updates", value=payload, key=sym.encode("utf-8"))

                # Write LINKED edges to Neo4j
                valid_links = [
                    {
                        "source_account": lk.source_account,
                        "target_account": lk.target_account,
                        "confidence": lk.confidence,
                        "methods": [m.value for m in lk.methods],
                        "evidence_ids": lk.evidence_ids,
                    }
                    for lk in links
                    if lk.is_finding
                ]
                await self.store.upsert_linked_edges(valid_links, case_id=f"case_{sym.lower()}")

            except Exception as exc:
                logger.error("Attribution cycle failed for symbol", symbol=sym, error=str(exc))

    async def stop(self) -> None:
        self.running = False
        await self._flush_trades()
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.redis_client:
            await self.redis_client.aclose()
        await self.store.close()
        logger.info("Attribution Service stopped cleanly")


async def run() -> None:
    setup_logging()
    svc = AttributionService()

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
