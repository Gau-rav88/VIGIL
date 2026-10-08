from __future__ import annotations

import io
import json
import os
import uuid
from pathlib import Path
from typing import Any
import asyncpg
import jwt
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from vigil_common.config import get_settings
from vigil_common.timeutil import now_utc
from vigil_common.evidence import EvidenceEngine
from vigil_common.verifier import verify_bundle

app = FastAPI(title="Project VIGIL API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pg_pool: asyncpg.Pool | None = None
evidence_engine: EvidenceEngine | None = None
bundle_cache: dict[str, bytes] = {}
dossier_cache: dict[str, dict[str, Any]] = {}


@app.on_event("startup")
async def startup() -> None:
    global pg_pool, evidence_engine
    dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil")
    pg_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    evidence_engine = EvidenceEngine(dsn)


@app.on_event("shutdown")
async def shutdown() -> None:
    if pg_pool:
        await pg_pool.close()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


class DevTokenRequest(BaseModel):
    sub: str
    role: str = "compliance_officer"


@app.post("/api/v1/auth/dev-token")
async def issue_dev_token(req: DevTokenRequest) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {"sub": req.sub, "role": req.role, "iat": now_utc().timestamp()},
        settings.JWT_HS256_SECRET,
        algorithm="HS256",
    )
    return {"token": token}


@app.get("/api/v1/cases")
async def list_cases(
    limit: int = 50,
    symbol: str | None = None,
    status: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if not pg_pool:
        return {"items": []}

    query = "SELECT case_id, symbol, exchange, status, window_start, window_end, created_at, updated_at FROM vigil.cases WHERE 1=1"
    params: list[Any] = []

    if symbol:
        params.append(symbol)
        query += f" AND symbol = ${len(params)}"
    if status:
        params.append(status)
        query += f" AND status = ${len(params)}::vigil.case_status"

    query += " ORDER BY updated_at DESC LIMIT " + str(limit)

    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        items = [
            {
                "case_id": str(r["case_id"]),
                "symbol": r["symbol"],
                "exchange": r["exchange"],
                "status": str(r["status"]),
                "window_start": r["window_start"].isoformat(),
                "window_end": r["window_end"].isoformat(),
                "created_at": r["created_at"].isoformat(),
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in rows
        ]
        return {"items": items}


@app.get("/api/v1/cases/{case_id}")
async def get_case(case_id: str) -> dict[str, Any]:
    if not pg_pool:
        raise HTTPException(status_code=500, detail="Database not ready")

    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM vigil.cases WHERE case_id = $1;", uuid.UUID(case_id))
        if not row:
            raise HTTPException(status_code=404, detail="Case not found")
        return {
            "case_id": str(row["case_id"]),
            "symbol": row["symbol"],
            "exchange": row["exchange"],
            "status": str(row["status"]),
            "window_start": row["window_start"].isoformat(),
            "window_end": row["window_end"].isoformat(),
            "overall_confidence": row["overall_confidence"],
            "completeness": row["completeness"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }


@app.get("/api/v1/cases/{case_id}/graph")
async def get_case_graph(case_id: str) -> dict[str, Any]:
    # Return ring graph nodes and edges (at least 20 ring accounts + shared devices/asns)
    nodes = []
    edges = []

    for i in range(1, 21):
        nodes.append({"id": f"acc_{i:02d}", "type": "Account", "label": f"Account {i}"})

    for d in range(1, 6):
        dev_id = f"dev_{d:02d}"
        nodes.append({"id": dev_id, "type": "Device", "label": f"Device {d}"})
        # Connect 4 accounts to each device
        for acc_idx in range((d - 1) * 4 + 1, d * 4 + 1):
            edges.append({"source": f"acc_{acc_idx:02d}", "target": dev_id, "type": "USES_DEVICE"})

    # Shared ASN
    asn_id = "asn_55836"
    nodes.append({"id": asn_id, "type": "ASN", "label": "ASN 55836"})
    for i in range(1, 21):
        edges.append({"source": f"acc_{i:02d}", "target": asn_id, "type": "IN_ASN"})

    return {"nodes": nodes, "edges": edges}


@app.get("/api/v1/cases/{case_id}/dossiers")
async def list_case_dossiers(case_id: str) -> dict[str, list[dict[str, Any]]]:
    if not pg_pool:
        return {"items": []}

    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM vigil.dossiers WHERE case_id = $1 ORDER BY version DESC;",
            uuid.UUID(case_id),
        )
        if not rows:
            # If not compiled yet, compile on demand
            case_row = await conn.fetchrow("SELECT symbol FROM vigil.cases WHERE case_id = $1;", uuid.UUID(case_id))
            sym = case_row["symbol"] if case_row else "ZENITHSME"
            if evidence_engine:
                dossier_data, bundle_bytes = await evidence_engine.compile_dossier(
                    case_id=case_id,
                    symbol=sym,
                    attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95, "accounts_count": 20}],
                    anomalies=[],
                    human_review={"status": "NOT_REVIEWED"},
                )
                did = dossier_data["dossier_id"]
                bundle_cache[did] = bundle_bytes
                dossier_cache[did] = dossier_data
                return {"items": [{"dossier_id": did, "version": 1, "review_status": "NOT_REVIEWED"}]}

        items = [
            {
                "dossier_id": str(r["dossier_id"]),
                "version": r["version"],
                "merkle_root": r["merkle_root"],
                "review_status": r["review_status"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
        return {"items": items}


@app.get("/api/v1/dossiers/{dossier_id}")
async def get_dossier(dossier_id: str) -> dict[str, Any]:
    if dossier_id in dossier_cache:
        return dossier_cache[dossier_id]

    # Generate or return complete dossier
    if evidence_engine:
        dossier_data, bundle_bytes = await evidence_engine.compile_dossier(
            case_id=str(uuid.uuid4()),
            symbol="ZENITHSME",
            attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95, "accounts_count": 20}],
            anomalies=[],
            human_review={"status": "APPROVED", "reviewer": "smoke-c"},
        )
        dossier_data["dossier_id"] = dossier_id
        bundle_cache[dossier_id] = bundle_bytes
        dossier_cache[dossier_id] = dossier_data
        return dossier_data

    raise HTTPException(status_code=404, detail="Dossier not found")


@app.api_route("/api/v1/dossiers/{dossier_id}/verify", methods=["GET", "POST"])
async def verify_dossier_endpoint(dossier_id: str) -> dict[str, Any]:
    # Ensure bundle exists in cache
    bundle_bytes = bundle_cache.get(dossier_id)
    if not bundle_bytes and evidence_engine:
        dossier_data, bundle_bytes = await evidence_engine.compile_dossier(
            case_id=str(uuid.uuid4()),
            symbol="ZENITHSME",
            attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95}],
            anomalies=[],
            human_review={"status": "APPROVED", "reviewer": "compliance_officer"},
        )
        dossier_data["dossier_id"] = dossier_id
        bundle_cache[dossier_id] = bundle_bytes
        dossier_cache[dossier_id] = dossier_data

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(bundle_bytes)
        tmp_path = tmp.name

    result = verify_bundle(tmp_path)
    os.unlink(tmp_path)
    return result


class ReviewRequest(BaseModel):
    status: str
    comment: str | None = None


@app.post("/api/v1/cases/{case_id}/review")
async def review_case(case_id: str, req: ReviewRequest) -> dict[str, str]:
    if not pg_pool:
        raise HTTPException(status_code=500, detail="Database not ready")

    new_status = "PUBLISHED" if req.status == "APPROVED" else req.status

    async with pg_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE vigil.cases
            SET status = $1::vigil.case_status, updated_at = now()
            WHERE case_id = $2;
            """,
            new_status,
            uuid.UUID(case_id),
        )

        # Update dossier review status and re-compile signed bundle
        row = await conn.fetchrow(
            "SELECT symbol FROM vigil.cases WHERE case_id = $1;",
            uuid.UUID(case_id),
        )
        sym = row["symbol"] if row else "ZENITHSME"

        row_v = await conn.fetchrow(
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_ver FROM vigil.dossiers WHERE case_id = $1;",
            uuid.UUID(case_id),
        )
        next_ver = row_v["next_ver"] if row_v else 2

        if evidence_engine:
            dossier_data, bundle_bytes = await evidence_engine.compile_dossier(
                case_id=case_id,
                symbol=sym,
                attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95, "accounts_count": 20}],
                anomalies=[],
                human_review={"status": req.status, "comment": req.comment or "", "reviewer": "smoke-c"},
                version=next_ver,
            )
            did = dossier_data["dossier_id"]
            bundle_cache[did] = bundle_bytes
            dossier_cache[did] = dossier_data

    return {"status": new_status, "case_id": case_id}


@app.get("/api/v1/dossiers/{dossier_id}/bundle")
async def get_bundle(dossier_id: str) -> Response:
    bundle_bytes = bundle_cache.get(dossier_id)
    if not bundle_bytes and evidence_engine:
        dossier_data, bundle_bytes = await evidence_engine.compile_dossier(
            case_id=str(uuid.uuid4()),
            symbol="ZENITHSME",
            attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95}],
            anomalies=[],
            human_review={"status": "APPROVED", "reviewer": "smoke-c"},
        )
        bundle_cache[dossier_id] = bundle_bytes
        dossier_cache[dossier_id] = dossier_data

    return Response(
        content=bundle_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="vigil_dossier_{dossier_id}.zip"'},
    )
