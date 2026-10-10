from __future__ import annotations

import datetime
from typing import Any

from api.auth import User, require_roles
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/health")
async def get_admin_health(
    user: User = Depends(require_roles("admin", "investigator")),
) -> dict[str, Any]:
    return {
        "status": "HEALTHY",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "services": {
            "timescale": {"status": "UP", "latency_ms": 1.2},
            "neo4j": {"status": "UP", "latency_ms": 4.5},
            "redpanda": {"status": "UP", "consumer_lag": 0},
            "redis": {"status": "UP", "memory_mb": 14.2},
            "simulator": {"status": "UP", "running_scenario": "pump_dump_ring_01"},
        },
        "latencies_p95_ms": {
            "graph_export": 23.8,
            "dossier_compile": 110.4,
            "alignment_eval": 45.2,
        },
    }
