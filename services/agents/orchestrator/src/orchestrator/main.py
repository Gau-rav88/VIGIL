from __future__ import annotations

import asyncio
import json
import os
import signal
import uuid
from typing import Any

import asyncpg
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from evidence_engine.builder import EvidenceEngine
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from neo4j import AsyncGraphDatabase
from vigil_common.logging import get_logger, setup_logging
from vigil_common.network import resolve_db_dsn, resolve_kafka_bootstrap, resolve_neo4j_uri

from orchestrator.bus import AgentToolBus
from orchestrator.graph import build_graph
from orchestrator.models import CaseState
from orchestrator.nodes import OrchestratorDeps

logger = get_logger("orchestrator")


class CaseOrchestrator:
    def __init__(self) -> None:
        self.kafka_bootstrap = resolve_kafka_bootstrap(os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092"))
        self.pg_dsn = resolve_db_dsn(os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil"))
        self.neo4j_uri = resolve_neo4j_uri(os.getenv("NEO4J_URI", "bolt://neo4j:7687"))
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "vigilneo4j")

        self.pool: asyncpg.Pool | None = None
        self.neo4j_driver: Any = None
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.evidence_engine: EvidenceEngine | None = None
        self.tool_bus: AgentToolBus | None = None
        self.deps: OrchestratorDeps | None = None
        self.graph: Any = None
        self.running = False
        self.checkpointer_cm: Any = None
        self.checkpointer: Any = None

    async def start(self) -> None:
        self.running = True
        logger.info("Starting LangGraph case orchestrator...", bootstrap=self.kafka_bootstrap)

        # 1. Initialize DB & Storage connections
        self.pool = await asyncpg.create_pool(self.pg_dsn, min_size=2, max_size=10)
        self.evidence_engine = EvidenceEngine(self.pg_dsn)
        self.tool_bus = AgentToolBus()
        await self.tool_bus.connect()

        try:
            self.neo4j_driver = AsyncGraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )
        except Exception:
            self.neo4j_driver = None

        # 2. Setup Postgres Checkpointer
        self.checkpointer_cm = AsyncPostgresSaver.from_conn_string(self.pg_dsn)
        self.checkpointer = await self.checkpointer_cm.__aenter__()
        await self.checkpointer.setup()

        # 3. Build LangGraph StateGraph
        self.deps = OrchestratorDeps(
            pg_dsn=self.pg_dsn,
            pool=self.pool,
            evidence_engine=self.evidence_engine,
            tool_bus=self.tool_bus,
            neo4j_driver=self.neo4j_driver,
        )
        self.graph = build_graph(self.deps, checkpointer=self.checkpointer)
        logger.info("LangGraph StateGraph compiled with PostgreSQL checkpointer")

        # 4. Start Kafka Consumers & Producers
        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            "case.trigger",
            "anomaly.fused",
            bootstrap_servers=self.kafka_bootstrap,
            group_id="orchestrator_workers_v2",
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Listening on case.trigger and anomaly.fused")

        async for record in self.consumer:
            if not self.running:
                break
            try:
                data = json.loads(record.value)
                await self._process_trigger(data)
            except Exception as exc:
                logger.error("Error processing trigger in orchestrator", error=str(exc))

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.tool_bus:
            await self.tool_bus.close()
        if self.pool:
            await self.pool.close()
        if self.checkpointer_cm:
            await self.checkpointer_cm.__aexit__(None, None, None)

    async def _process_trigger(self, anom: dict[str, Any]) -> None:
        sym = anom.get("symbol", "UNKNOWN")
        anom_id = anom.get("anomaly_id", str(uuid.uuid4()))
        anom_type = anom.get("type", "CROSS_MODAL_ALIGNMENT")

        logger.info("Orchestrator received anomaly event", symbol=sym, anomaly_type=anom_type)

        # Simulation and real-time triggers are processed immediately


        # Check existing active case in DB
        case_id = await self._get_active_case_for_symbol(sym)
        if case_id:
            logger.info("Active case already exists for symbol", symbol=sym, case_id=case_id)
            return

        if anom_type not in ("CROSS_MODAL_ALIGNMENT", "CIRCULAR_RING", "FINGERPRINT_CLUSTER", "PUMP_AND_DUMP"):
            return

        # Generate new case ID
        new_case_id = str(uuid.uuid4())
        init_state: CaseState = {
            "case_id": new_case_id,
            "symbol": sym,
            "exchange": "SYNTH",
            "trigger_anomaly_id": anom_id,
            "stage": "OPENED",
        }

        config = {"configurable": {"thread_id": new_case_id}}
        logger.info("Invoking LangGraph for new case", case_id=new_case_id, symbol=sym)

        # Run state graph until interrupt() at await_review
        try:
            state = await self.graph.ainvoke(init_state, config=config)
            logger.info(
                "Case traversed LangGraph state machine",
                case_id=new_case_id,
                stage=state.get("stage"),
                dossier_id=state.get("dossier_id"),
            )
        except Exception as exc:
            logger.error("LangGraph execution error", case_id=new_case_id, error=str(exc))

    async def resume_case(self, case_id: str, review_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Resumes a paused case after human compliance review action.
        """
        if not self.graph:
            raise RuntimeError("Graph not initialized")

        config = {"configurable": {"thread_id": case_id}}
        resumed_state = await self.graph.ainvoke(Command(resume=review_payload), config=config)
        return dict(resumed_state)

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


async def run_service() -> None:
    setup_logging()
    orchestrator = CaseOrchestrator()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(orchestrator.stop()))

    try:
        await orchestrator.start()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(run_service())
