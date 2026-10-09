from __future__ import annotations

import asyncio
import datetime
import json
import os
import signal
import uuid
from pathlib import Path
from typing import Any

import asyncpg
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from neo4j import AsyncGraphDatabase
from vigil_common.evidence import EvidenceEngine
from vigil_common.logging import get_logger, setup_logging

logger = get_logger("orchestrator")


class CaseOrchestrator:
    def __init__(self) -> None:
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.pg_dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil")
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "vigilneo4j")

        self.pool: asyncpg.Pool | None = None
        self.neo4j_driver: Any = None
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.evidence_engine: EvidenceEngine | None = None
        self.running = False
        self.active_cases: dict[str, str] = {}  # symbol -> case_id

    async def start(self) -> None:
        self.running = True
        logger.info("Starting orchestrator agent...", bootstrap=self.kafka_bootstrap)

        self.pool = await asyncpg.create_pool(self.pg_dsn, min_size=2, max_size=10)
        self.neo4j_driver = AsyncGraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        self.evidence_engine = EvidenceEngine(self.pg_dsn)

        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            "case.trigger",
            "anomaly.fused",
            bootstrap_servers=self.kafka_bootstrap,
            group_id="orchestrator_workers",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Connected to case.trigger and anomaly.fused")

        async for record in self.consumer:
            if not self.running:
                break
            try:
                data = json.loads(record.value)
                await self._process_trigger(data)
            except Exception as exc:
                logger.error("Error processing trigger in orchestrator", error=str(exc))

    async def _process_trigger(self, anom: dict[str, Any]) -> None:
        sym = anom.get("symbol", "UNKNOWN")
        anom_id = anom.get("anomaly_id", str(uuid.uuid4()))
        anom_type = anom.get("type", "CROSS_MODAL_ALIGNMENT")

        logger.info("Orchestrator received case trigger", symbol=sym, anomaly_type=anom_type)

        # Ignore stale triggers from previous runs
        det_at = anom.get("detected_at")
        if det_at:
            try:
                det_dt = datetime.datetime.fromisoformat(det_at.replace("Z", "+00:00"))
                age_s = (datetime.datetime.now(datetime.timezone.utc) - det_dt).total_seconds()
                if age_s > 60.0:
                    logger.info("Ignoring stale trigger", symbol=sym, age_s=round(age_s, 1))
                    return
            except Exception:
                pass

        # Check existing active case in DB
        case_id = await self._get_active_case_for_symbol(sym)
        if case_id:
            return  # Case already opened or in review; do not overwrite!

        if anom_type != "CROSS_MODAL_ALIGNMENT":
            return  # Single modality anomalies do not open cases
        case_id = await self._create_case(sym, anom_id)

        # Expand attribution graph in Neo4j
        rings = await self._query_graph_rings(sym)

        # Compile dossier
        if self.evidence_engine:
            dossier_data, bundle_bytes = await self.evidence_engine.compile_dossier(
                case_id=case_id,
                symbol=sym,
                attribution_rings=rings,
                anomalies=[anom],
                human_review={"status": "NOT_REVIEWED"},
            )

            # Store bundle locally / in cache
            bundle_dir = Path("/tmp/vigil_bundles")
            bundle_dir.mkdir(parents=True, exist_ok=True)
            with open(bundle_dir / f"{dossier_data['dossier_id']}.zip", "wb") as f:
                f.write(bundle_bytes)

            # Transition case status to PENDING_REVIEW
            await self._update_case_status(case_id, "PENDING_REVIEW")
            logger.info("Case transitioned to PENDING_REVIEW", case_id=case_id, symbol=sym)

    async def _get_active_case_for_symbol(self, symbol: str) -> str | None:
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT case_id FROM vigil.cases
                WHERE symbol = $1 AND status NOT IN ('CLOSED_NO_ACTION', 'PUBLISHED', 'REJECTED')
                ORDER BY updated_at DESC LIMIT 1;
                """,
                symbol,
            )
            return str(row["case_id"]) if row else None

    async def _create_case(self, symbol: str, trigger_anom_id: str) -> str:
        if not self.pool:
            return ""
        case_id = str(uuid.uuid4())
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        start_dt = now_dt - datetime.timedelta(hours=1)

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO vigil.cases (
                    case_id, symbol, exchange, status, window_start, window_end, trigger_anomaly_id,
                    mrs, overall_confidence, completeness, state, is_synthetic
                ) VALUES ($1, $2, $3, 'OPENED'::vigil.case_status, $4, $5, $6, $7, $8, $9, $10, true);
                """,
                uuid.UUID(case_id),
                symbol,
                "SYNTH",
                start_dt,
                now_dt,
                uuid.UUID(trigger_anom_id),
                0.85,
                0.92,
                0.90,
                json.dumps({"stage": "OPENED", "symbol": symbol}),
            )
        logger.info("Opened new forensic case", case_id=case_id, symbol=symbol)
        return case_id

    async def _update_case_status(self, case_id: str, new_status: str) -> None:
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE vigil.cases
                SET status = $1::vigil.case_status, updated_at = now()
                WHERE case_id = $2;
                """,
                new_status,
                uuid.UUID(case_id),
            )

    async def _query_graph_rings(self, symbol: str) -> list[dict[str, Any]]:
        if not self.neo4j_driver:
            return [{"ring_id": "ring_01", "ring_score": 0.95, "accounts_count": 20}]

        query = """
        MATCH (a1:Account)-[:USES_DEVICE]->(d:Device)<-[:USES_DEVICE]-(a2:Account)
        WITH collect(DISTINCT a1.account_id) + collect(DISTINCT a2.account_id) AS accs
        RETURN size(accs) AS sz
        LIMIT 1
        """
        try:
            async with self.neo4j_driver.session() as session:
                res = await session.run(query)
                rec = await res.single()
                sz = rec["sz"] if rec else 20
                return [{
                    "ring_id": "ring_01",
                    "ring_score": 0.92,
                    "accounts_count": max(15, sz),
                    "shared_devices": 5,
                    "shared_asn": 55836,
                }]
        except Exception:
            return [{
                "ring_id": "ring_01",
                "ring_score": 0.92,
                "accounts_count": 20,
                "shared_devices": 5,
                "shared_asn": 55836,
            }]

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        if self.pool:
            await self.pool.close()
        logger.info("Orchestrator stopped cleanly")


async def run() -> None:
    setup_logging()
    orchestrator = CaseOrchestrator()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(orchestrator.start())

    await stop_event.wait()
    await orchestrator.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
