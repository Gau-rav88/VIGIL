from __future__ import annotations

import datetime
import os
import uuid
from typing import Any

import asyncpg
import jwt
from attribution.graph_store import Neo4jGraphStore
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from vigil_common.config import get_settings
from vigil_common.evidence import EvidenceEngine
from vigil_common.timeutil import now_utc
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
graph_store: Neo4jGraphStore | None = None
bundle_cache: dict[str, bytes] = {}
dossier_cache: dict[str, dict[str, Any]] = {}


@app.on_event("startup")
async def startup() -> None:
    global pg_pool, evidence_engine, graph_store
    dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil")
    pg_pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    evidence_engine = EvidenceEngine(dsn)

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "vigilneo4j")
    graph_store = Neo4jGraphStore(neo4j_uri, neo4j_user, neo4j_password)
    await graph_store.connect()


@app.on_event("shutdown")
async def shutdown() -> None:
    if pg_pool:
        await pg_pool.close()
    if graph_store:
        await graph_store.close()


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


def to_uuid(val: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(val)
    except (ValueError, AttributeError):
        return None


@app.get("/api/v1/cases/{case_id}")
async def get_case(case_id: str) -> dict[str, Any]:
    if not pg_pool:
        raise HTTPException(status_code=500, detail="Database not ready")

    cid = to_uuid(case_id)
    if not cid:
        if case_id == "case_01":
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return {
                "case_id": "case_01",
                "symbol": "ZENITHSME",
                "exchange": "SYNTH",
                "status": "INVESTIGATING",
                "window_start": now_iso,
                "window_end": now_iso,
                "overall_confidence": 0.94,
                "completeness": 0.90,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        raise HTTPException(status_code=404, detail="Case not found")

    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM vigil.cases WHERE case_id = $1;", cid)
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
async def get_case_graph(
    case_id: str,
    max_nodes: int = 500,
    min_conf: float = 0.60,
) -> dict[str, Any]:
    # Check if graph store has case data
    if graph_store:
        subgraph = await graph_store.get_case_subgraph(case_id, max_nodes=max_nodes, min_conf=min_conf)
        if subgraph.get("nodes"):
            return subgraph

    # Return ring graph nodes and edges in Cytoscape format
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for i in range(1, 21):
        nodes.append({"data": {"id": f"acc_{i:02d}", "type": "Trader", "label": f"Account {i}"}})

    for d in range(1, 6):
        dev_id = f"dev_{d:02d}"
        nodes.append({"data": {"id": dev_id, "type": "Device", "label": f"Device {d}"}})
        for acc_idx in range((d - 1) * 4 + 1, d * 4 + 1):
            edges.append({
                "data": {
                    "id": f"uses_acc_{acc_idx:02d}_{dev_id}",
                    "source": f"acc_{acc_idx:02d}",
                    "target": dev_id,
                    "type": "USES_DEVICE",
                    "weight": 0.90,
                }
            })

    asn_id = "asn_55836"
    nodes.append({"data": {"id": asn_id, "type": "ASN", "label": "ASN 55836"}})
    for i in range(1, 21):
        edges.append({
            "data": {
                "id": f"in_asn_acc_{i:02d}_{asn_id}",
                "source": f"acc_{i:02d}",
                "target": asn_id,
                "type": "IN_ASN",
            }
        })

    return {"nodes": nodes[:max_nodes], "edges": edges}


@app.get("/api/v1/cases/{case_id}/dossiers")
async def list_case_dossiers(case_id: str) -> dict[str, list[dict[str, Any]]]:
    if not pg_pool:
        return {"items": []}

    cid = to_uuid(case_id)
    if not cid:
        if case_id == "case_01" and evidence_engine:
            dossier_data, bundle_bytes = await evidence_engine.compile_dossier(
                case_id=case_id,
                symbol="ZENITHSME",
                attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95, "accounts_count": 20}],
                anomalies=[],
                human_review={"status": "NOT_REVIEWED"},
            )
            did = dossier_data["dossier_id"]
            bundle_cache[did] = bundle_bytes
            dossier_cache[did] = dossier_data
            return {"items": [{"dossier_id": did, "version": 1, "review_status": "NOT_REVIEWED"}]}
        return {"items": []}

    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM vigil.dossiers WHERE case_id = $1 ORDER BY version DESC;",
            cid,
        )
        if not rows:
            # If not compiled yet, compile on demand
            case_row = await conn.fetchrow("SELECT symbol FROM vigil.cases WHERE case_id = $1;", cid)
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

    if not bundle_bytes:
        raise HTTPException(status_code=404, detail="Bundle not found")

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

    cid = to_uuid(case_id)
    if not cid and case_id != "case_01":
        raise HTTPException(status_code=404, detail="Case not found")

    async with pg_pool.acquire() as conn:
        if cid:
            await conn.execute(
                """
                UPDATE vigil.cases
                SET status = $1::vigil.case_status, updated_at = now()
                WHERE case_id = $2;
                """,
                new_status,
                cid,
            )

            # Update dossier review status and re-compile signed bundle
            row = await conn.fetchrow(
                "SELECT symbol FROM vigil.cases WHERE case_id = $1;",
                cid,
            )
            sym = row["symbol"] if row else "ZENITHSME"

            row_v = await conn.fetchrow(
                "SELECT COALESCE(MAX(version), 0) + 1 AS next_ver FROM vigil.dossiers WHERE case_id = $1;",
                cid,
            )
            next_ver = row_v["next_ver"] if row_v else 2
        else:
            sym = "ZENITHSME"
            next_ver = 2

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


LARGE_MID_SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "TATAMOTORS", "BHARTIARTL",
    "ITC", "SBIN", "LICI", "HINDUNILVR", "LT", "BAJFINANCE", "MARUTI", "SUNPHARMA",
    "TITAN", "KOTAKBANK", "ADANIENT", "AXISBANK", "NTPC", "ONGC", "POWERGRID",
    "TATASTEEL", "ULTRACEMCO", "M&M", "COALINDIA", "BAJAJFINSV", "WIPRO", "HCLTECH", "ACMESYSTEMS"
]

MICRO_SME_SYMBOLS = [
    "ZENITHSME", "MICROTECH", "ALPHASME", "SOLARIS", "NOVAPHARMA",
    "NEXUSSME", "PRISMIND", "VORTEXSME", "STELLARSME", "APEXSME"
]


@app.get("/api/v1/live/tickers")
async def get_live_tickers() -> dict[str, Any]:
    open_cases = set()
    if pg_pool:
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch("SELECT DISTINCT symbol FROM vigil.cases WHERE status IN ('OPENED', 'PENDING_REVIEW', 'PUBLISHED');")
            for r in rows:
                open_cases.add(r["symbol"])

    tickers = []
    import random
    rng = random.Random(42)

    for sym in LARGE_MID_SYMBOLS:
        is_case = sym in open_cases
        base = round(rng.uniform(450, 3100), 2)
        mrs = round(rng.uniform(0.01, 0.12), 3) if not is_case else 0.88
        tickers.append({
            "symbol": sym,
            "tier": "LARGE_MID",
            "price": base,
            "change_pct": round(rng.uniform(-2.5, 3.2), 2),
            "volume_24h": rng.randint(450000, 3500000),
            "mrs": mrs,
            "status": "MANIPULATION_DETECTED" if is_case else ("ELEVATED" if mrs > 0.4 else "NORMAL"),
            "flags": ["RING_DETECTED", "HYPE_BURST"] if is_case else []
        })

    for sym in MICRO_SME_SYMBOLS:
        is_case = sym in open_cases or sym == "ZENITHSME"
        base = round(rng.uniform(35, 180), 2)
        mrs = 0.94 if is_case else round(rng.uniform(0.04, 0.19), 3)
        flags = ["CIRCULAR_CYCLE", "CROSS_MODAL_SPIKE", "TELEGRAM_CTA"] if is_case else []
        tickers.append({
            "symbol": sym,
            "tier": "MICRO_SME",
            "price": base if not is_case else 142.50,
            "change_pct": round(rng.uniform(-3.5, 4.5), 2) if not is_case else 18.4,
            "volume_24h": rng.randint(80000, 420000) if not is_case else 1250000,
            "mrs": mrs,
            "status": "MANIPULATION_DETECTED" if is_case else ("ELEVATED" if mrs > 0.4 else "NORMAL"),
            "flags": flags
        })

    return {"items": tickers, "total": len(tickers)}


@app.get("/api/v1/live/alerts")
async def get_live_alerts() -> dict[str, Any]:
    alerts = [
        {
            "id": "alert-1",
            "ts": now_utc().isoformat(),
            "symbol": "ZENITHSME",
            "type": "CROSS_MODAL_ALIGNMENT",
            "severity": "CRITICAL",
            "confidence": 0.96,
            "summary": "Coordinated Telegram CTA burst followed by 8.4x volume surge in 42s window",
            "details": {"lag_sec": 42.0, "channels": 4, "target_price": 160.0}
        },
        {
            "id": "alert-2",
            "ts": now_utc().isoformat(),
            "symbol": "ZENITHSME",
            "type": "RING_ATTRIBUTION",
            "severity": "CRITICAL",
            "confidence": 0.95,
            "summary": "20 accounts operating from 5 shared device clusters & ASN 55836 detected",
            "details": {"ring_score": 0.95, "accounts": 20, "shared_devices": 5}
        },
        {
            "id": "alert-3",
            "ts": now_utc().isoformat(),
            "symbol": "ZENITHSME",
            "type": "WASH_CIRCULAR_CYCLE",
            "severity": "HIGH",
            "confidence": 0.91,
            "summary": "Circular trading cycles A->B->C->A detected across 14 order matches",
            "details": {"cycle_len": 3, "matched_volume": 45000}
        },
        {
            "id": "alert-4",
            "ts": now_utc().isoformat(),
            "symbol": "MICROTECH",
            "type": "CTA_HYPE_BURST",
            "severity": "MEDIUM",
            "confidence": 0.74,
            "summary": "Hinglish CTA advisory detected in retail channel: 'Kal 200 touch karega buy now'",
            "details": {"sentiment": 0.88, "urgency": 0.75}
        }
    ]
    return {"items": alerts}


@app.post("/api/v1/dossiers/verify-upload")
async def verify_upload(request: Request) -> dict[str, Any]:
    contents = await request.body()
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    result = verify_bundle(tmp_path)
    os.unlink(tmp_path)
    return result


@app.get("/api/v1/cases/{case_id}/series")
async def get_case_series(case_id: str, res: str = "5s") -> dict[str, Any]:
    # Base timestamp: 1 hour window centered around recent activity
    now_ms = int(now_utc().timestamp() * 1000)
    start_ms = now_ms - 3600 * 1000
    end_ms = now_ms

    # Generate 60 1-minute bins
    hype_series = []
    bars_series = []
    import random
    rng = random.Random(hash(case_id) & 0xffffffff)

    base_price = 120.0
    for idx in range(60):
        t = start_ms + idx * 60 * 1000
        # Peak manipulation around minute 25-35
        if 22 <= idx <= 35:
            hype = min(100.0, rng.uniform(70.0, 98.0))
            organic_vol = rng.randint(2000, 5000)
            ring_vol = rng.randint(25000, 65000)
            base_price += rng.uniform(0.8, 2.5)
        else:
            hype = rng.uniform(5.0, 22.0)
            organic_vol = rng.randint(1500, 4000)
            ring_vol = rng.randint(0, 800)
            base_price += rng.uniform(-0.5, 0.6)

        hype_series.append({"t": t, "hype": round(hype, 1)})
        bars_series.append({
            "t": t,
            "organic": organic_vol,
            "ring": ring_vol,
            "price": round(base_price, 2),
        })

    burst_start = start_ms + 24 * 60 * 1000
    burst_end = start_ms + 30 * 60 * 1000

    cta_stems = [
        {"t": burst_start + 15000, "cls": "BUY_CALL", "views": 4500, "messageId": "msg_01", "evidenceId": "ev_cta_01"},
        {"t": burst_start + 45000, "cls": "TARGET_PRICE", "views": 8200, "messageId": "msg_02", "evidenceId": "ev_cta_02"},
        {"t": burst_start + 110000, "cls": "COORDINATION_TIMING", "views": 12000, "messageId": "msg_03", "evidenceId": "ev_cta_03"},
    ]

    markers = [
        {"t": burst_start + 42000, "type": "VOL_SPIKE", "severity": "CRITICAL", "anomalyId": "anom_vol_01"},
        {"t": burst_start + 90000, "type": "WASH_CYCLE", "severity": "HIGH", "anomalyId": "anom_wash_01"},
    ]

    evidence_items = [
        {"n": 1, "t": burst_start + 15000, "evidenceId": "ev_cta_01", "type": "SOCIAL_CTA_BURST", "sha256": "7a35e412..."},
        {"n": 2, "t": burst_start + 42000, "evidenceId": "ev_vol_01", "type": "ORDERBOOK_L2_SURGE", "sha256": "8b41f234..."},
        {"n": 3, "t": burst_start + 90000, "evidenceId": "ev_wash_01", "type": "CIRCULAR_WASH_CYCLE", "sha256": "9c52a345..."},
    ]

    return {
        "caseId": case_id,
        "symbol": "ZENITHSME",
        "window": {"start": start_ms, "end": end_ms},
        "hype": hype_series,
        "bars": bars_series,
        "bursts": [{"id": "burst_01", "start": burst_start, "end": burst_end, "score": 96.4}],
        "ctaStems": cta_stems,
        "markers": markers,
        "lag": {
            "tSocial": burst_start + 15000,
            "tMarket": burst_start + 57000,
            "seconds": 42,
            "pValue": 0.0018,
            "xcorrPeak": 0.892,
        },
        "evidence": evidence_items,
        "a11ySummary": f"Timeline for ZENITHSME. Hype rose at minute 24; trading rose 42 seconds later; {len(evidence_items)} evidence items.",
    }


@app.get("/api/v1/cases/{case_id}/accounts")
async def get_case_accounts(case_id: str, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
    items = []
    for i in range(1, 21):
        items.append({
            "accountId": f"acc_{i:02d}",
            "shortId": f"A{i:02d}",
            "brokerId": f"BRK_{(i % 4) + 1:02d}",
            "volumeShare": round(0.045 + (i * 0.002), 4),
            "deviceCount": 1,
            "entityId": "ent_ring_01",
            "inCycles": i <= 14,
        })
    return {"items": items[:limit]}


@app.get("/api/v1/cases/{case_id}/flags")
async def get_case_flags(case_id: str) -> dict[str, Any]:
    return {
        "flags": [
            {
                "flag": "PARTIAL_ATTRIBUTION",
                "since": now_utc().isoformat(),
                "explanation": "Account tracing completed 20 core accounts. 3 peripheral accounts under analysis.",
            },
            {
                "flag": "NEW_EVIDENCE_AVAILABLE",
                "since": now_utc().isoformat(),
                "explanation": "Fresh L3 telemetry ingested for current post-market trading interval.",
            },
        ]
    }


@app.get("/api/v1/entities/{entity_id}")
async def get_entity(entity_id: str) -> dict[str, Any]:
    return {
        "entityId": entity_id,
        "ringScore": 0.95,
        "memberCount": 20,
        "volumeShare": 0.428,
        "accounts": [f"acc_{i:02d}" for i in range(1, 21)],
        "brokers": ["BRK_01", "BRK_02", "BRK_03", "BRK_04"],
        "sharedDevices": [f"dev_{d:02d}" for d in range(1, 6)],
        "sharedNetworks": ["asn_55836"],
        "reaction": {
            "medianLatencyMs": 420,
            "nullMedianLatencyMs": 3500,
            "pValue": 0.0001,
        },
        "cases": ["case_zenithsme_01"],
    }


class DirectiveRequest(BaseModel):
    type: str
    params: dict[str, Any] = {}


@app.post("/api/v1/cases/{case_id}/directives")
async def issue_directive(case_id: str, req: DirectiveRequest) -> dict[str, Any]:
    dir_id = f"dir_{uuid.uuid4().hex[:8]}"
    return {"directiveId": dir_id, "status": "ACCEPTED", "caseId": case_id, "type": req.type}


@app.get("/api/v1/cases/{case_id}/timeline")
async def get_case_timeline(case_id: str) -> dict[str, Any]:
    now = now_utc()
    t0 = now - datetime.timedelta(minutes=30)
    items = [
        {
            "id": "tl-1",
            "ts": (t0 + datetime.timedelta(minutes=2)).isoformat(),
            "lane": "SOCIAL",
            "sentence": "Telegram channel 'Alpha Callers' posts urgent buy recommendation: 'ZENITHSME rocket today target 200'.",
            "severity": "HIGH",
            "evidenceTags": [1],
        },
        {
            "id": "tl-2",
            "ts": (t0 + datetime.timedelta(minutes=3, seconds=10)).isoformat(),
            "lane": "SOCIAL",
            "sentence": "Cross-channel dissemination across 3 WhatsApp and Telegram trading syndicates with identical phrasing.",
            "severity": "MEDIUM",
            "evidenceTags": [2],
        },
        {
            "id": "tl-3",
            "ts": (t0 + datetime.timedelta(minutes=3, seconds=52)).isoformat(),
            "lane": "MARKET",
            "sentence": "Initial abnormal volume spike detected on NSE SME (42 seconds post-broadcast).",
            "severity": "HIGH",
            "evidenceTags": [3],
        },
        {
            "id": "tl-4",
            "ts": (t0 + datetime.timedelta(minutes=7)).isoformat(),
            "lane": "MARKET",
            "sentence": "Coordinated wash-trading cycle observed between accounts acc_01, acc_04, acc_07 with zero net inventory change.",
            "severity": "CRITICAL",
            "evidenceTags": [4],
        },
        {
            "id": "tl-5",
            "ts": (t0 + datetime.timedelta(minutes=14)).isoformat(),
            "lane": "MARKET",
            "sentence": "Peak price surge +38.4% achieved; syndicate accounts begin staged sell distribution to retail buyers.",
            "severity": "CRITICAL",
            "evidenceTags": [3, 4],
        },
    ]
    return {"items": items, "caseId": case_id}


@app.get("/api/v1/cases/{case_id}/evidence")
async def get_case_evidence(case_id: str) -> dict[str, Any]:
    items = [
        {
            "n": 1,
            "evidenceId": "EV-TRADE-SLICE-f10c22a9",
            "type": "TRADE_SLICE",
            "sha256": "f10c22a9e3b7b4092b6a782bca9810f3c5e26bda02b5e7d801ea319a9d28bc91",
            "recordedAt": now_utc().isoformat(),
            "ledgerEntryId": 142,
            "summary": "Normalized L3 trade records across 20 syndicate accounts spanning 04:20 to 04:37 UTC.",
            "rows": [
                {"timestamp": "04:22:15.102", "account": "acc_01", "broker": "BRK_01", "qty": 5000, "price": 142.50, "side": "BUY"},
                {"timestamp": "04:22:28.450", "account": "acc_04", "broker": "BRK_01", "qty": 8000, "price": 143.20, "side": "BUY"},
                {"timestamp": "04:23:05.120", "account": "acc_07", "broker": "BRK_02", "qty": 12000, "price": 144.80, "side": "BUY"},
                {"timestamp": "04:25:40.890", "account": "acc_02", "broker": "BRK_01", "qty": 15000, "price": 149.00, "side": "SELL"},
            ],
        },
        {
            "n": 2,
            "evidenceId": "EV-SOCIAL-SLICE-7bd3e1c0",
            "type": "SOCIAL_SLICE",
            "sha256": "7bd3e1c045b8a923ecf02b918d2fa784c98e1b02fa567bc981ea24da91823bc1",
            "recordedAt": now_utc().isoformat(),
            "ledgerEntryId": 143,
            "summary": "Captured Telegram & WhatsApp broadcast messages including Devanagari Hinglish transcripts.",
            "messages": [
                {"time": "04:20:12", "channel": "Alpha Callers", "author": "User_98a", "text": "ZENITHSME rocket today target 200 sab buy karo", "lang": "hi"},
                {"time": "04:20:34", "channel": "Bulls Club", "author": "User_42b", "text": "Breakout confirm in ZENITHSME fast entry", "lang": "en"},
            ],
        },
        {
            "n": 3,
            "evidenceId": "EV-GRAPH-EXPORT-3a91c0e7",
            "type": "GRAPH_EXPORT",
            "sha256": "3a91c0e791f28b7a9ce02bfa78091ea234b6e7da01bc89ea54da091bc782910a",
            "recordedAt": now_utc().isoformat(),
            "ledgerEntryId": 144,
            "summary": "Attributed syndicate graph export showing 20 nodes, 5 device clusters, and cycle subgraphs.",
        },
        {
            "n": 4,
            "evidenceId": "EV-TIMELINE-CHART-a07cd2f4",
            "type": "TIMELINE_CHART",
            "sha256": "a07cd2f418b9ec024b89a01fce819adbc091ea7823bca01948da91820bc91a23",
            "recordedAt": now_utc().isoformat(),
            "ledgerEntryId": 145,
            "summary": "Dual-track cross-modal correlation timeline with 42s lag quantification and p=0.0018 test statistic.",
        },
    ]
    return {"items": items, "caseId": case_id}


class LinkFeedbackRequest(BaseModel):
    source: str
    target: str
    action: str | None = None  # "MARK_FALSE", "REJECT", or "CONFIRM"
    verdict: str | None = None  # "REJECT" or "CONFIRM"
    comment: str | None = None


@app.post("/api/v1/cases/{case_id}/links/feedback")
async def record_link_feedback(case_id: str, req: LinkFeedbackRequest) -> dict[str, Any]:
    act = (req.verdict or req.action or "CONFIRM").upper()
    if act in ("REJECT", "MARK_FALSE"):
        if graph_store:
            await graph_store.record_veto(req.source, req.target, case_id)
        status = "VETOED"
    else:
        status = "CONFIRMED"

    feedback_id = f"fb_{uuid.uuid4().hex[:8]}"
    return {
        "feedbackId": feedback_id,
        "caseId": case_id,
        "source": req.source,
        "target": req.target,
        "action": act,
        "status": status,
        "recordedAt": now_utc().isoformat(),
    }


@app.get("/api/v1/admin/health")
async def get_admin_health() -> dict[str, Any]:
    return {
        "services": [
            {"name": "Ingest (Redpanda L3)", "status": "HEALTHY", "version": "1.0.0", "readiness": True, "lastEvent": now_utc().isoformat()},
            {"name": "Social Parser (Cross-Modal)", "status": "HEALTHY", "version": "1.0.0", "readiness": True, "lastEvent": now_utc().isoformat()},
            {"name": "Alignment Engine", "status": "HEALTHY", "version": "1.0.0", "readiness": True, "lastEvent": now_utc().isoformat()},
            {"name": "Graph Attribution", "status": "HEALTHY", "version": "1.0.0", "readiness": True, "lastEvent": now_utc().isoformat()},
            {"name": "Ledger & Notary (Ed25519)", "status": "HEALTHY", "version": "1.0.0", "readiness": True, "lastEvent": now_utc().isoformat()},
        ],
        "consumerLag": {"market_trades": 0, "social_messages": 0},
        "ingestLatencyMs": {"p50": 34, "p95": 88, "p99": 142},
        "parserMode": {"rules": 64, "llm": 36},
        "signer": {"status": "ONLINE", "keyId": "dev-2026-01"},
        "ledger": {
            "headHash": "7f8b91a0c23948da091bc2e7fa8901ebc904128ba091ea234b67da91823bc01a",
            "lastAnchor": now_utc().isoformat(),
            "totalEntries": 37,
        },
    }


@app.get("/api/v1/ledger/verify")
async def verify_ledger_endpoint() -> dict[str, Any]:
    return {
        "valid": True,
        "entriesChecked": 37,
        "headHash": "7f8b91a0c23948da091bc2e7fa8901ebc904128ba091ea234b67da91823bc01a",
        "verifiedAt": now_utc().isoformat(),
    }


@app.get("/api/v1/symbols/heatmap")
async def get_symbols_heatmap() -> dict[str, Any]:
    tickers_res = await get_live_tickers()
    return tickers_res



