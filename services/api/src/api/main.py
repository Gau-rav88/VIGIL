from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from attribution.graph_store import Neo4jGraphStore
from evidence_engine.builder import EvidenceEngine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from vigil_common.config import get_settings
from vigil_common.network import resolve_db_dsn, resolve_neo4j_uri

import api.deps as deps
from api.errors import register_error_handlers
from api.routers import (
    accounts,
    admin,
    anomalies,
    auth,
    cases,
    dossiers,
    evidence,
    health,
    ledger,
    sim,
    social,
    symbols,
    verify,
    ws,
)

logger = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    # Enforce security gate: refuse ENV=prod with default/weak JWT secrets
    if settings.ENV == "prod":
        default_secrets = {
            "dev_jwt_secret_change_in_production_32chars_min",
            "secret",
            "changeme",
        }
        if settings.JWT_HS256_SECRET in default_secrets or len(settings.JWT_HS256_SECRET) < 32:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: Cannot start API with ENV=prod and default or short (<32 chars) JWT_HS256_SECRET."
            )

    # 1. Initialize Postgres / Timescale Pool with bounded retry
    dsn = resolve_db_dsn(os.getenv("PG_DSN"))
    for attempt in range(1, 4):
        try:
            deps.pg_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, timeout=5.0)
            logger.info(f"Successfully connected to TimescaleDB pool: {dsn}")
            break
        except Exception as exc:
            logger.warning(
                f"TimescaleDB connection attempt {attempt} failed: {exc}",
                exc_info=True,
            )
            deps.pg_pool = None
            if attempt < 3:
                await asyncio.sleep(1.0 * attempt)

    # 2. Initialize Evidence Engine
    try:
        deps.evidence_engine = EvidenceEngine(dsn, db_pool=deps.pg_pool)
    except Exception as exc:
        logger.warning(f"Could not initialize EvidenceEngine in lifespan: {exc}", exc_info=True)
        deps.evidence_engine = None

    # 3. Initialize Neo4j Graph Store with bounded retry
    neo4j_uri = resolve_neo4j_uri(os.getenv("NEO4J_URI"))
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "vigilneo4j")

    for attempt in range(1, 4):
        try:
            deps.graph_store = Neo4jGraphStore(neo4j_uri, neo4j_user, neo4j_password)
            await deps.graph_store.connect()
            logger.info(f"Successfully connected to Neo4j graph store: {neo4j_uri}")
            break
        except Exception as exc:
            logger.warning(
                f"Neo4j connection attempt {attempt} failed: {exc}",
                exc_info=True,
            )
            deps.graph_store = None
            if attempt < 3:
                await asyncio.sleep(1.0 * attempt)

    yield

    # Shutdown
    if deps.pg_pool:
        await deps.pg_pool.close()
    if deps.graph_store:
        await deps.graph_store.close()


app = FastAPI(
    title="Project VIGIL API",
    version="1.0.0",
    description="Serving plane for market manipulation forensic intelligence",
    lifespan=lifespan,
)

cors_origins_raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register RFC 7807 error handlers
register_error_handlers(app)

# Include Modular Routers per P7-T01
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(symbols.router)
app.include_router(anomalies.router)
app.include_router(social.router)
app.include_router(cases.router)
app.include_router(evidence.router)
app.include_router(dossiers.router)
app.include_router(verify.router)
app.include_router(ledger.router)
app.include_router(accounts.router)
app.include_router(admin.router)
app.include_router(sim.router)
app.include_router(ws.router)
