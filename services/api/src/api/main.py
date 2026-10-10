from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from attribution.graph_store import Neo4jGraphStore
from evidence_engine.builder import EvidenceEngine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil")
    try:
        deps.pg_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    except Exception:
        # Local development fallback
        try:
            deps.pg_pool = await asyncpg.create_pool("postgresql://vigil:vigil@localhost:5434/vigil", min_size=2, max_size=10)
        except Exception:
            deps.pg_pool = None

    try:
        deps.evidence_engine = EvidenceEngine(dsn)
    except Exception:
        deps.evidence_engine = None

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "vigilneo4j")
    try:
        deps.graph_store = Neo4jGraphStore(neo4j_uri, neo4j_user, neo4j_password)
        await deps.graph_store.connect()
    except Exception:
        try:
            deps.graph_store = Neo4jGraphStore("bolt://localhost:7687", neo4j_user, neo4j_password)
            await deps.graph_store.connect()
        except Exception:
            deps.graph_store = None

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
