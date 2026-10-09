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
from neo4j import AsyncGraphDatabase
from vigil_common.logging import get_logger, setup_logging
from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

logger = get_logger("attribution")


class AttributionAgent:
    def __init__(self) -> None:
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "vigilneo4j")
        self.driver: Any = None
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.running = False
        self.trade_batch: list[dict[str, Any]] = []
        self.config_hash = hashlib.sha256(b"attribution_v1").hexdigest()

    async def start(self) -> None:
        self.running = True
        logger.info("Starting attribution agent...", neo4j=self.neo4j_uri)

        self.driver = AsyncGraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password),
        )
        logger.info("Connected to Neo4j")

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
        logger.info("Connected to market.trades.norm")

        periodic_task = asyncio.create_task(self._periodic_ring_scan())

        try:
            async for record in self.consumer:
                if not self.running:
                    break
                try:
                    data = json.loads(record.value)
                    self.trade_batch.append(data)
                    if len(self.trade_batch) >= 100:
                        await self._flush_trades()
                except Exception as exc:
                    logger.error("Error ingesting trade into graph", error=str(exc))
        finally:
            periodic_task.cancel()
            try:
                await periodic_task
            except asyncio.CancelledError:
                pass

    async def _flush_trades(self) -> None:
        if not self.trade_batch or not self.driver:
            return

        batch = self.trade_batch
        self.trade_batch = []

        query = """
        UNWIND $batch AS row
        MERGE (buyer:Account {account_id: row.buyer.account_id})
          ON CREATE SET buyer.broker_id = row.buyer.broker_id
        MERGE (seller:Account {account_id: row.seller.account_id})
          ON CREATE SET seller.broker_id = row.seller.broker_id

        FOREACH (_ IN CASE WHEN row.buyer.device_fp IS NOT NULL THEN [1] ELSE [] END |
          MERGE (b_dev:Device {device_fp: row.buyer.device_fp})
          MERGE (buyer)-[:USES_DEVICE]->(b_dev)
        )
        FOREACH (_ IN CASE WHEN row.seller.device_fp IS NOT NULL THEN [1] ELSE [] END |
          MERGE (s_dev:Device {device_fp: row.seller.device_fp})
          MERGE (seller)-[:USES_DEVICE]->(s_dev)
        )
        FOREACH (_ IN CASE WHEN row.buyer.asn IS NOT NULL THEN [1] ELSE [] END |
          MERGE (b_asn:ASN {asn: row.buyer.asn})
          MERGE (buyer)-[:IN_ASN]->(b_asn)
        )
        FOREACH (_ IN CASE WHEN row.seller.asn IS NOT NULL THEN [1] ELSE [] END |
          MERGE (s_asn:ASN {asn: row.seller.asn})
          MERGE (seller)-[:IN_ASN]->(s_asn)
        )

        CREATE (buyer)-[:TRADED_WITH {
          symbol: row.symbol,
          trade_id: row.trade_id,
          qty: row.qty,
          price: row.price,
          ts: row.ts_exchange
        }]->(seller)
        """

        try:
            async with self.driver.session() as session:
                await session.run(query, batch=batch)
        except Exception as exc:
            logger.error("Failed to write trade batch to Neo4j", error=str(exc))

    async def _periodic_ring_scan(self) -> None:
        while self.running:
            await asyncio.sleep(5.0)
            await self._flush_trades()
            await self._scan_rings()

    async def _scan_rings(self) -> None:
        if not self.driver:
            return

        # 1. Device clusters (shared devices)
        device_query = """
        MATCH (a1:Account)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(a2:Account)
        WHERE a1.account_id < a2.account_id
        WITH d, collect(DISTINCT a1.account_id) + collect(DISTINCT a2.account_id) AS accs
        WHERE size(accs) >= 2
        RETURN d.device_fp AS device, accs
        LIMIT 10
        """

        # 2. Wash trading cycles
        cycle_query = """
        MATCH path = (a1:Account)-[t:TRADED_WITH*2..4]->(a1:Account)
        WITH [n IN nodes(path) | n.account_id] AS ring, length(path) AS cycle_len
        RETURN ring, cycle_len
        LIMIT 10
        """

        try:
            async with self.driver.session() as session:
                # Scan device clusters
                res = await session.run(device_query)
                records = await res.data()
                for rec in records:
                    accs = list(set(rec["accs"]))
                    if len(accs) >= 4:
                        await self._emit_graph_anomaly(
                            anom_type="FINGERPRINT_CLUSTER",
                            participants=accs,
                            metrics={"shared_device": rec["device"], "cluster_size": len(accs)},
                            score=0.95,
                        )

                # Scan wash trade cycles
                res_cycles = await session.run(cycle_query)
                cycle_records = await res_cycles.data()
                for rec in cycle_records:
                    ring = list(set(rec["ring"]))
                    if len(ring) >= 2:
                        await self._emit_graph_anomaly(
                            anom_type="CIRCULAR_RING",
                            participants=ring,
                            metrics={"cycle_len": rec["cycle_len"], "ring_size": len(ring)},
                            score=0.98,
                        )
        except Exception as exc:
            logger.error("Error in graph ring scan", error=str(exc))

    async def _emit_graph_anomaly(
        self,
        anom_type: str,
        participants: list[str],
        metrics: dict[str, Any],
        score: float,
    ) -> None:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        start_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=120)).isoformat()

        anom = AnomalyEvent(
            schema_version="1.0.0",
            anomaly_id=str(uuid.uuid4()),
            type=anom_type,  # type: ignore[arg-type]
            source_agent="attribution",
            symbol="ZENITHSME",  # or from trade
            window_start=start_iso,
            window_end=now_iso,
            score=score,
            severity="HIGH" if score >= 0.9 else "MEDIUM",
            metrics=metrics,
            participants=participants,
            evidence_refs=[EvidenceRef(kind="anomaly_id", ref=str(uuid.uuid4()))],
            detector_version="1.0.0",
            config_hash=self.config_hash,
            detected_at=now_iso,
        )

        if self.producer:
            payload = json.dumps(anom.model_dump()).encode("utf-8")
            await self.producer.send(topic="anomaly.fused", value=payload, key=b"attribution")
            await self.producer.send(topic="graph.updates", value=payload, key=b"attribution")

    async def stop(self) -> None:
        self.running = False
        await self._flush_trades()
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.driver:
            await self.driver.close()
        logger.info("Attribution agent stopped cleanly")


async def run() -> None:
    setup_logging()
    agent = AttributionAgent()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(agent.start())

    await stop_event.wait()
    await agent.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
