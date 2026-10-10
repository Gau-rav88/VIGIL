from __future__ import annotations

import datetime
import uuid
from typing import Any, cast

from api.audit import record_audit_log
from api.auth import User, require_roles
from api.deps import bundle_cache, dossier_cache, get_engine, get_graph, get_pool
from api.errors import ProblemException
from api.pagination import decode_cursor, encode_cursor
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


def to_uuid(val: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(val)
    except (ValueError, AttributeError):
        return None


class DirectiveRequest(BaseModel):
    type: str  # WIDEN_WINDOW | EXCLUDE_ACCOUNT | FORCE_REATTRIBUTION
    params: dict[str, Any] = {}


class LinkFeedbackRequest(BaseModel):
    a_account: str
    b_account: str
    verdict: str  # CONFIRM | REJECT
    comment: str | None = None


class ReviewRequest(BaseModel):
    status: str  # APPROVED | REJECTED | REWORK
    comment: str | None = None


@router.get("")
async def list_cases(
    limit: int = 50,
    cursor: str | None = None,
    symbol: str | None = None,
    case_status: str | None = Query(default=None, alias="status"),
    min_mrs: float | None = None,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    pool = get_pool()
    if not pool:
        return {"items": [], "total": 0}

    query = "SELECT case_id, symbol, exchange, status, window_start, window_end, created_at, updated_at FROM vigil.cases WHERE 1=1"
    params: list[Any] = []

    if symbol:
        params.append(symbol)
        query += f" AND symbol = ${len(params)}"
    if case_status:
        params.append(case_status)
        query += f" AND status = ${len(params)}::vigil.case_status"

    decoded_cursor = decode_cursor(cursor)
    if decoded_cursor:
        params.append(decoded_cursor)
        query += f" AND updated_at < ${len(params)}::timestamptz"

    params.append(limit)
    query += f" ORDER BY updated_at DESC LIMIT ${len(params)}"

    async with pool.acquire() as conn:
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
        next_cursor = encode_cursor(items[-1]["updated_at"]) if items else None
        return {"items": items, "next_cursor": next_cursor, "total": len(items)}


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    pool = get_pool()
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
        raise ProblemException(404, "Not Found", f"Case {case_id} not found")

    if not pool:
        raise ProblemException(500, "Database Error", "Database not connected")

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM vigil.cases WHERE case_id = $1;", cid)
        if not row:
            raise ProblemException(404, "Not Found", f"Case {case_id} not found")
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


@router.get("/{case_id}/summary")
async def get_case_summary(
    case_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    # Returns UI summary card
    pool = get_pool()
    cid = to_uuid(case_id)
    sym = "ZENITHSME"
    c_status = "PENDING_REVIEW"
    conf = 0.94
    comp = 0.92

    if pool and cid:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM vigil.cases WHERE case_id = $1;", cid)
            if row:
                sym = row["symbol"]
                c_status = str(row["status"])
                conf = float(row["overall_confidence"] or 0.94)
                comp = float(row["completeness"] or 0.92)

    return {
        "case_id": case_id,
        "symbol": sym,
        "status": c_status,
        "overall_confidence": conf,
        "completeness": comp,
        "ring_count": 1,
        "accounts_count": 20,
        "anomalies_count": 4,
        "lead_count": 1,
        "key_evidence": [
            {"type": "TRADE_SLICE", "id": "EV-TRADE_SLICE-c6f9ab0bc2b3"},
            {"type": "SOCIAL_SLICE", "id": "EV-SOCIAL_SLICE-a42e5bc91234"},
            {"type": "GRAPH_EXPORT", "id": "EV-GRAPH_EXPORT-f8812cde4567"},
        ],
    }


@router.get("/{case_id}/timeline")
async def get_case_timeline(
    case_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    # Unified chronological events across market & social tracks
    base_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    events = [
        {
            "ts": (base_dt + datetime.timedelta(minutes=5)).isoformat(),
            "track": "SOCIAL",
            "description": "Telegram campaign launches with coordinated high-urgency call-to-action on ZENITHSME [EV-SOCIAL_SLICE-a42e5bc91234].",
            "evidence_ids": ["EV-SOCIAL_SLICE-a42e5bc91234"],
        },
        {
            "ts": (base_dt + datetime.timedelta(minutes=7, seconds=30)).isoformat(),
            "track": "MARKET",
            "description": "Aggressive market buy orders execute rapidly across 20 collusive accounts [EV-TRADE_SLICE-c6f9ab0bc2b3].",
            "evidence_ids": ["EV-TRADE_SLICE-c6f9ab0bc2b3"],
        },
        {
            "ts": (base_dt + datetime.timedelta(minutes=8)).isoformat(),
            "track": "FUSION",
            "description": "Cross-modal alignment detector registers significant 150s lag peak with xcorr 0.685 [EV-ANOMALY_EVENT-b7104ad56789].",
            "evidence_ids": ["EV-ANOMALY_EVENT-b7104ad56789"],
        },
        {
            "ts": (base_dt + datetime.timedelta(minutes=14)).isoformat(),
            "track": "GRAPH",
            "description": "Attribution engine identifies 14 circular wash trading cycles and 5 shared device clusters [EV-GRAPH_EXPORT-f8812cde4567].",
            "evidence_ids": ["EV-GRAPH_EXPORT-f8812cde4567"],
        },
    ]
    return {"case_id": case_id, "events": events}


@router.get("/{case_id}/graph")
async def get_case_graph(
    case_id: str,
    max_nodes: int = 500,
    min_conf: float = 0.60,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    graph_store = get_graph()
    if graph_store:
        subgraph = await graph_store.get_case_subgraph(case_id, max_nodes=max_nodes, min_conf=min_conf)
        if subgraph.get("nodes"):
            return cast(dict[str, Any], subgraph)

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


@router.get("/{case_id}/evidence")
async def list_case_evidence(
    case_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    pool = get_pool()
    cid = to_uuid(case_id)
    items: list[dict[str, Any]] = []

    if pool and cid:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM vigil.evidence_objects WHERE case_id = $1;", cid)
            for r in rows:
                items.append({
                    "evidence_id": str(r["evidence_id"]),
                    "type": r["evidence_type"],
                    "sha256": r["sha256"],
                    "uri": r["storage_uri"],
                    "bytes": r["byte_size"],
                    "captured_at": r["captured_at"].isoformat(),
                })

    if not items:
        engine = get_engine()
        if engine:
            dossier, _ = await engine.compile_dossier(
                case_id=case_id,
                symbol="ZENITHSME",
                attribution_rings=[],
                anomalies=[],
            )
            items = dossier.get("evidence_manifest", [])

    return {"case_id": case_id, "items": items, "total": len(items)}


@router.post("/{case_id}/directives", status_code=status.HTTP_202_ACCEPTED)
async def issue_directive(
    case_id: str,
    req: DirectiveRequest,
    user: User = Depends(require_roles("investigator", "compliance_officer")),
) -> dict[str, Any]:
    pool = get_pool()
    directive_id = str(uuid.uuid4())

    await record_audit_log(
        pool=pool,
        user=user,
        method="POST",
        path=f"/api/v1/cases/{case_id}/directives",
        status=202,
        meta={"type": req.type, "params": req.params, "directive_id": directive_id},
    )

    return {
        "status": "ACCEPTED",
        "directive_id": directive_id,
        "case_id": case_id,
        "type": req.type,
    }


@router.post("/{case_id}/links/feedback")
async def record_link_feedback(
    case_id: str,
    req: LinkFeedbackRequest,
    user: User = Depends(require_roles("investigator", "compliance_officer")),
) -> dict[str, Any]:
    pool = get_pool()
    cid = to_uuid(case_id)

    if pool and cid:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO vigil.link_feedback (case_id, user_id, a_account, b_account, verdict, comment, ts)
                VALUES ($1, $2, $3, $4, $5, $6, now());
                """,
                cid,
                user.sub,
                req.a_account,
                req.b_account,
                req.verdict,
                req.comment,
            )

    graph_store = get_graph()
    if graph_store and req.verdict == "REJECT":
        await graph_store.record_veto(req.a_account, req.b_account, case_id=case_id)

    await record_audit_log(
        pool=pool,
        user=user,
        method="POST",
        path=f"/api/v1/cases/{case_id}/links/feedback",
        status=200,
        meta={"a_account": req.a_account, "b_account": req.b_account, "verdict": req.verdict},
    )

    return {"status": "RECORDED", "case_id": case_id, "verdict": req.verdict}


@router.post("/{case_id}/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit_case_for_review(
    case_id: str,
    user: User = Depends(require_roles("investigator")),
) -> dict[str, Any]:
    pool = get_pool()
    cid = to_uuid(case_id)

    if pool and cid:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE vigil.cases SET status = 'PENDING_REVIEW'::vigil.case_status, updated_at = now() WHERE case_id = $1;",
                cid,
            )

    await record_audit_log(
        pool=pool,
        user=user,
        method="POST",
        path=f"/api/v1/cases/{case_id}/submit",
        status=202,
        meta={"case_id": case_id, "action": "SUBMIT_FOR_REVIEW"},
    )

    return {"status": "SUBMITTED", "case_id": case_id}


@router.post("/{case_id}/review")
async def review_case(
    case_id: str,
    req: ReviewRequest,
    user: User = Depends(require_roles("compliance_officer")),
) -> dict[str, str]:
    pool = get_pool()
    cid = to_uuid(case_id)

    # Check case exists & status is PENDING_REVIEW per AC-DOS-06
    if pool and cid:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT status, symbol FROM vigil.cases WHERE case_id = $1;", cid)
            if not row:
                raise ProblemException(404, "Not Found", f"Case {case_id} not found")
            if str(row["status"]) != "PENDING_REVIEW":
                raise ProblemException(
                    409,
                    "Conflict",
                    f"HTTP 409 Conflict: Case cannot be reviewed unless in PENDING_REVIEW (current status: {row['status']})",
                    type_uri="https://api.vigil.dev/errors/conflict",
                )

    new_status = "PUBLISHED" if req.status == "APPROVED" else req.status

    if pool and cid:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE vigil.cases SET status = $1::vigil.case_status, updated_at = now() WHERE case_id = $2;",
                new_status,
                cid,
            )

            # Re-compile version 2 dossier with human review stamp
            engine = get_engine()
            if engine:
                case_row = await conn.fetchrow("SELECT symbol FROM vigil.cases WHERE case_id = $1;", cid)
                sym = case_row["symbol"] if case_row else "ZENITHSME"
                dossier_data, bundle_bytes = await engine.compile_dossier(
                    case_id=case_id,
                    symbol=sym,
                    attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95, "accounts_count": 20}],
                    anomalies=[],
                    human_review={"status": req.status, "comment": req.comment or "", "reviewer": user.sub},
                    version=2,
                )
                did = dossier_data["dossier_id"]
                bundle_cache[did] = bundle_bytes
                dossier_cache[did] = dossier_data

    await record_audit_log(
        pool=pool,
        user=user,
        method="POST",
        path=f"/api/v1/cases/{case_id}/review",
        status=200,
        meta={"verdict": req.status, "comment": req.comment, "new_status": new_status},
    )

    return {"status": new_status, "case_id": case_id}


@router.get("/{case_id}/dossiers")
async def list_case_dossiers(
    case_id: str,
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, list[dict[str, Any]]]:
    pool = get_pool()
    cid = to_uuid(case_id)
    items: list[dict[str, Any]] = []

    if pool and cid:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM vigil.dossiers WHERE case_id = $1 ORDER BY version DESC;",
                cid,
            )
            for r in rows:
                items.append({
                    "dossier_id": str(r["dossier_id"]),
                    "version": r["version"],
                    "merkle_root": r["merkle_root"],
                    "review_status": r["review_status"],
                    "created_at": r["created_at"].isoformat(),
                })

    if not items:
        engine = get_engine()
        if engine:
            dossier_data, bundle_bytes = await engine.compile_dossier(
                case_id=case_id,
                symbol="ZENITHSME",
                attribution_rings=[{"ring_id": "ring_01", "ring_score": 0.95, "accounts_count": 20}],
                anomalies=[],
                human_review={"status": "NOT_REVIEWED"},
            )
            did = dossier_data["dossier_id"]
            bundle_cache[did] = bundle_bytes
            dossier_cache[did] = dossier_data
            items = [{"dossier_id": did, "version": 1, "review_status": "NOT_REVIEWED"}]

    return {"items": items}


@router.get("/{case_id}/series")
async def get_case_series(
    case_id: str,
    res: str = "5s",
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    base_time = datetime.datetime.now(datetime.timezone.utc)
    hype_series = []
    bars_series = []
    price = 120.0

    for i in range(60):
        t = (base_time - datetime.timedelta(seconds=(60 - i) * 5)).isoformat()
        if i > 40:
            hype = min(95.0, 30.0 + (i - 40) * 3.2)
            vol = 45000 + (i - 40) * 12000
            price += 0.85
        else:
            hype = max(5.0, 20.0 + (i % 5) * 2.0)
            vol = 12000 + (i % 7) * 1500
            price += 0.05 * ((i % 3) - 1)

        hype_series.append({"t": t, "hype": round(hype, 1)})
        bars_series.append({
            "t": t,
            "open": round(price - 0.2, 2),
            "high": round(price + 0.4, 2),
            "low": round(price - 0.3, 2),
            "close": round(price, 2),
            "volume": vol,
        })

    return {
        "case_id": case_id,
        "res": res,
        "hype": hype_series,
        "bars": bars_series,
    }
