from __future__ import annotations

import os
from typing import Any

import asyncpg
from attribution.graph_store import Neo4jGraphStore
from evidence_engine.builder import EvidenceEngine

pg_pool: asyncpg.Pool | None = None
evidence_engine: EvidenceEngine | None = None
graph_store: Neo4jGraphStore | None = None
bundle_cache: dict[str, bytes] = {}
dossier_cache: dict[str, dict[str, Any]] = {}


def get_pool() -> asyncpg.Pool | None:
    return pg_pool


def get_engine() -> EvidenceEngine:
    global evidence_engine
    if evidence_engine is None:
        dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@localhost:5434/vigil")
        evidence_engine = EvidenceEngine(dsn)
    return evidence_engine


def get_graph() -> Neo4jGraphStore | None:
    return graph_store
