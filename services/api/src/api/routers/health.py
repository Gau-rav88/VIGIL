from __future__ import annotations

import asyncio
import os
from typing import Any

import redis.asyncio as aioredis
from aiokafka.admin import AIOKafkaAdminClient
from api.deps import get_graph, get_pool
from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from vigil_common.network import (
    resolve_kafka_bootstrap,
    resolve_redis_url,
    resolve_s3_endpoint,
)
from vigil_common.topics import Topics

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> JSONResponse:
    deps_status: dict[str, dict[str, Any]] = {
        "timescale": {"status": "DOWN", "required": True},
        "redis": {"status": "DOWN", "required": True},
        "kafka": {"status": "DOWN", "required": True},
        "neo4j": {"status": "DOWN", "required": True},
        "minio": {"status": "DOWN", "required": True},
    }

    async def check_timescale() -> None:
        pool = get_pool()
        if pool is not None:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("SELECT 1;")
                deps_status["timescale"] = {"status": "UP", "required": True}
            except Exception as exc:
                deps_status["timescale"] = {"status": "DOWN", "required": True, "error": str(exc)}
        else:
            deps_status["timescale"] = {"status": "DOWN", "required": True, "error": "Pool not initialized"}

    async def check_redis() -> None:
        redis_url = resolve_redis_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        try:
            r = aioredis.from_url(redis_url, socket_timeout=2.0)
            await r.ping()
            await r.close()
            deps_status["redis"] = {"status": "UP", "required": True}
        except Exception as exc:
            deps_status["redis"] = {"status": "DOWN", "required": True, "error": str(exc)}

    async def check_kafka() -> None:
        bootstrap = resolve_kafka_bootstrap(os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092"))
        admin: AIOKafkaAdminClient | None = None
        try:
            admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap, request_timeout_ms=3000)
            await admin.start()
            await admin.describe_cluster()
            topics = await admin.list_topics()
            required_topics = set(Topics.all_topics())
            missing = required_topics - set(topics)
            if missing:
                deps_status["kafka"] = {
                    "status": "DOWN",
                    "required": True,
                    "error": f"Missing required topics: {list(missing)}",
                }
            else:
                deps_status["kafka"] = {"status": "UP", "required": True}
        except Exception as exc:
            deps_status["kafka"] = {"status": "DOWN", "required": True, "error": str(exc)}
        finally:
            if admin:
                await admin.close()

    async def check_neo4j() -> None:
        graph = get_graph()
        if graph and graph.driver:
            try:
                async with graph.driver.session() as s:
                    res = await s.run("RETURN 1 AS ok")
                    await res.single()
                deps_status["neo4j"] = {"status": "UP", "required": True}
            except Exception as exc:
                deps_status["neo4j"] = {"status": "DOWN", "required": True, "error": str(exc)}
        else:
            deps_status["neo4j"] = {"status": "DOWN", "required": True, "error": "Neo4j driver not connected"}

    async def check_minio() -> None:
        import httpx

        s3_url = resolve_s3_endpoint(os.getenv("S3_ENDPOINT", "http://minio:9000"))
        health_url = f"{s3_url.rstrip('/')}/minio/health/live"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(health_url)
                if res.status_code == 200:
                    deps_status["minio"] = {"status": "UP", "required": True}
                else:
                    deps_status["minio"] = {"status": "DOWN", "required": True, "status_code": res.status_code}
        except Exception as exc:
            deps_status["minio"] = {"status": "DOWN", "required": True, "error": str(exc)}

    await asyncio.gather(
        check_timescale(),
        check_redis(),
        check_kafka(),
        check_neo4j(),
        check_minio(),
        return_exceptions=True,
    )

    all_up = all(d["status"] == "UP" for d in deps_status.values() if d.get("required"))
    status_code = 200 if all_up else 503
    payload = {
        "status": "ready" if all_up else "degraded",
        "dependencies": deps_status,
    }
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
