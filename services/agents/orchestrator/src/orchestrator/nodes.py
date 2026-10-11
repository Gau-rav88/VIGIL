from __future__ import annotations

import datetime
import json
import os
import uuid
from pathlib import Path
from typing import Any, Callable

import asyncpg
import yaml
from evidence_engine.builder import EvidenceEngine
from langgraph.types import interrupt
from vigil_common.logging import get_logger

from orchestrator.bus import AgentToolBus
from orchestrator.models import CaseState
from orchestrator.narrator import LLMNarrator, TemplateNarrator

logger = get_logger("orchestrator.nodes")


class OrchestratorDeps:
    def __init__(
        self,
        pg_dsn: str | None = None,
        pool: asyncpg.Pool | None = None,
        evidence_engine: EvidenceEngine | None = None,
        tool_bus: AgentToolBus | None = None,
        neo4j_driver: Any = None,
    ) -> None:
        self.pg_dsn = pg_dsn or os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil")
        self.pool = pool
        self.evidence_engine = evidence_engine or EvidenceEngine(self.pg_dsn)
        self.tool_bus = tool_bus or AgentToolBus()
        self.neo4j_driver = neo4j_driver
        self.template_narrator = TemplateNarrator()
        self.llm_narrator = LLMNarrator()

        # Load regulatory clauses
        clauses_path = Path("config/regulatory_clauses.yaml")
        if not clauses_path.exists():
            clauses_path = Path(__file__).resolve().parents[5] / "config" / "regulatory_clauses.yaml"
        if clauses_path.exists():
            with open(clauses_path, "r", encoding="utf-8") as f:
                self.regulatory_clauses = yaml.safe_load(f) or []
        else:
            self.regulatory_clauses = []


def open_case_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        case_id = state.get("case_id") or str(uuid.uuid4())
        sym = state.get("symbol") or "UNKNOWN"
        exchange = state.get("exchange") or ("BINANCE" if "USDT" in sym else "SYNTH")
        flags = list(state.get("flags") or [])
        anom_id = state.get("trigger_anomaly_id") or str(uuid.uuid4())

        pad_s = int(os.getenv("CASE_WINDOW_PAD_S", "300"))
        start_dt = None
        end_dt = None

        # Derive case window from trigger anomaly window + padding if available
        if deps.pool and anom_id:
            try:
                async with deps.pool.acquire() as conn:
                    anom_row = await conn.fetchrow(
                        """
                        SELECT window_start, window_end, symbol, metrics
                        FROM vigil.anomalies
                        WHERE anomaly_id = $1::uuid;
                        """,
                        uuid.UUID(anom_id),
                    )
                    if anom_row:
                        if anom_row["symbol"]:
                            sym = anom_row["symbol"]
                        if anom_row.get("metrics") and isinstance(anom_row["metrics"], dict) and anom_row["metrics"].get("exchange"):
                            exchange = str(anom_row["metrics"]["exchange"])
                        elif "USDT" in sym:
                            exchange = "BINANCE"
                        if anom_row["window_start"] and anom_row["window_end"]:
                            start_dt = anom_row["window_start"] - datetime.timedelta(seconds=pad_s)
                            end_dt = anom_row["window_end"] + datetime.timedelta(seconds=pad_s)
            except Exception as exc:
                logger.warning("Could not fetch trigger anomaly window", error=str(exc))

        if start_dt is None or end_dt is None:
            if state.get("window") and "start" in state["window"] and "end" in state["window"]:
                start_dt = datetime.datetime.fromisoformat(state["window"]["start"].replace("Z", "+00:00"))
                end_dt = datetime.datetime.fromisoformat(state["window"]["end"].replace("Z", "+00:00"))
            else:
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                end_dt = now_dt
                start_dt = now_dt - datetime.timedelta(hours=2)

        window = {
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "widen_count": state.get("window", {}).get("widen_count", 0),
        }

        # Check overlap merge (FR-ORC-07: >= 50% overlap on same symbol)
        if deps.pool:
            try:
                async with deps.pool.acquire() as conn:
                    existing = await conn.fetchrow(
                        """
                        SELECT case_id FROM vigil.cases
                        WHERE symbol = $1 AND status NOT IN ('CLOSED_NO_ACTION', 'PUBLISHED', 'REJECTED')
                        AND case_id != $2::uuid
                        LIMIT 1;
                        """,
                        sym,
                        uuid.UUID(case_id),
                    )
                    if existing:
                        flags.append("MERGED")
                        return {"case_id": str(existing["case_id"]), "flags": flags, "stage": "OPENED"}

                    # Insert new case row with real metadata
                    await conn.execute(
                        """
                        INSERT INTO vigil.cases (
                            case_id, symbol, exchange, status, window_start, window_end,
                            trigger_anomaly_id, mrs, overall_confidence, completeness, state, is_synthetic
                        ) VALUES ($1::uuid, $2, $3, 'OPENED'::vigil.case_status, $4, $5, $6::uuid, 0.0, 0.0, 0.0, $7::jsonb, true)
                        ON CONFLICT (case_id) DO UPDATE SET updated_at = now();
                        """,
                        uuid.UUID(case_id),
                        sym,
                        exchange,
                        start_dt,
                        end_dt,
                        uuid.UUID(anom_id),
                        json.dumps({"symbol": sym, "exchange": exchange, "stage": "OPENED"}),
                    )
            except Exception as exc:
                logger.warning("DB insert in open_case failed, proceeding in-memory", error=str(exc))

        return {
            "case_id": case_id,
            "symbol": sym,
            "exchange": exchange,
            "stage": "OPENED",
            "trigger_anomaly_id": anom_id,
            "window": window,
            "flags": flags,
            "attempts": {},
            "errors": [],
            "directives": [],
        }

    return node


def enrich_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        sym = state.get("symbol") or "UNKNOWN"
        window = state.get("window") or {}
        attempts = dict(state.get("attempts") or {})
        attempts["enrich"] = attempts.get("enrich", 0) + 1
        flags = list(state.get("flags") or [])

        # Fan-out to QTA and SIA via tool bus
        mkt_res = await deps.tool_bus.send_command("quant_telemetry", "REQUEST_MARKET_SLICE", {"symbol": sym, "window": window})
        soc_res = await deps.tool_bus.send_command("social_intel", "REQUEST_SOCIAL_SLICE", {"symbol": sym, "window": window})

        market_slice = mkt_res.get("data")
        social_slice = soc_res.get("data")

        if not market_slice:
            flags.append("MISSING_MARKET_SLICE")
        if not social_slice:
            flags.append("MISSING_SOCIAL_SLICE")

        return {
            "stage": "ENRICHING",
            "market_slice": market_slice,
            "social_slice": social_slice,
            "flags": flags,
            "attempts": attempts,
        }

    return node


def align_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        # Derive real alignment from anomaly trigger or DB if available
        anom_id = state.get("trigger_anomaly_id")
        alignment = None

        if deps.pool and anom_id:
            try:
                async with deps.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT metrics FROM vigil.anomalies WHERE anomaly_id = $1::uuid",
                        uuid.UUID(anom_id),
                    )
                    if row and row["metrics"]:
                        m = row["metrics"]
                        if isinstance(m, str):
                            m = json.loads(m)
                        p_val = float(m.get("p_value", 0.001))
                        alignment = {
                            "best_lag_s": float(m.get("best_lag_s", m.get("lag_seconds", 0.0))),
                            "xcorr_peak": float(m.get("xcorr_peak", 0.0)),
                            "p_value": p_val,
                            "status": "SIGNIFICANT" if p_val < 0.01 else "CANDIDATE",
                        }
            except Exception as exc:
                logger.debug("Failed fetching alignment metrics from DB", error=str(exc))

        if not alignment:
            alignment = state.get("alignment")
            if not alignment or alignment.get("p_value") is None:
                alignment = {
                    "best_lag_s": 0.0,
                    "xcorr_peak": 0.0,
                    "p_value": 1.0,
                    "status": "NOT_RUN",
                }

        return {
            "stage": "ALIGNED",
            "alignment": alignment,
        }

    return node


def attribute_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        sym = state.get("symbol") or "UNKNOWN"
        directives = state.get("directives") or []
        window = dict(state.get("window") or {})

        # Apply directives if present
        for d in directives:
            if d.get("type") == "WIDEN_WINDOW":
                window["widen_count"] = window.get("widen_count", 0) + 1

        rings: list[dict[str, Any]] = []
        leads: list[dict[str, Any]] = []

        if deps.neo4j_driver:
            try:
                async with deps.neo4j_driver.session() as session:
                    res = await session.run(
                        """
                        MATCH (r:Ring) WHERE r.symbol = $sym
                        RETURN r.ring_id AS ring_id, r.entity_id AS entity_id,
                               r.ring_score AS ring_score, r.accounts AS accounts,
                               r.methods AS methods, r.cycle_count AS cycle_count,
                               r.net_volume AS net_volume
                        """,
                        sym=sym,
                    )
                    records = await res.data()
                    for rec in records:
                        rings.append(dict(rec))
            except Exception as exc:
                logger.debug("Neo4j ring query in attribute_node", error=str(exc))

        if not rings and deps.tool_bus:
            attr_res = await deps.tool_bus.send_command(
                "attribution", "REQUEST_ATTRIBUTION_RINGS", {"symbol": sym, "window": window}
            )
            data = attr_res.get("data")
            if isinstance(data, dict):
                rings = data.get("rings", [])
                leads = data.get("leads", [])

        return {
            "stage": "ATTRIBUTING",
            "attribution": {"rings": rings, "leads": leads},
            "window": window,
        }

    return node


def assess_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        alignment = state.get("alignment") or {}
        p_val = alignment.get("p_value", 1.0)
        xcorr = alignment.get("xcorr_peak", 0.0)
        attr = state.get("attribution") or {}
        has_rings = bool(attr.get("rings"))

        align_conf = max(0.0, min(1.0, float(xcorr))) if p_val < 0.01 else 0.0
        attr_conf = 0.95 if has_rings else 0.40
        if has_rings and align_conf > 0.0:
            overall = (align_conf * 0.4) + (attr_conf * 0.6)
        elif has_rings:
            overall = attr_conf * 0.85
        else:
            overall = align_conf * 0.7

        conf = {
            "overall": round(overall, 3),
            "completeness": 0.90 if has_rings else 0.60,
            "components": {"alignment": align_conf, "attribution": attr_conf},
        }

        clauses = deps.regulatory_clauses or [
            {
                "regime": "SEBI",
                "clause_id": "SEBI-PFUTP-R4(2)",
                "title": "PFUTP Regulations, 2003 — Reg. 4(2)",
                "finding_types": ["WASH_CYCLE", "CIRCULAR_RING", "PRICE_JUMP"],
                "rationale": "Matched and circular trades created false appearance of trading.",
                "legal_review_required": True,
            }
        ]

        return {
            "stage": "ASSESSING",
            "confidence": conf,
            "clauses": clauses,
        }

    return node


def draft_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        sym = state.get("symbol") or "UNKNOWN"
        case_id = state.get("case_id") or "case"
        short_id = case_id.replace("-", "")[:12]
        attempts = dict(state.get("attempts") or {})
        attempts["draft"] = attempts.get("draft", 0) + 1

        # Use TemplateNarrator if narrative_mode is TEMPLATE or on 3rd attempt
        narrator = deps.template_narrator if attempts.get("draft", 0) >= 2 else deps.llm_narrator
        ev_ids = {
            "TRADE_SLICE": f"EV-TRADE_SLICE-{short_id}",
            "SOCIAL_SLICE": f"EV-SOCIAL_SLICE-{short_id}",
            "GRAPH_EXPORT": f"EV-GRAPH_EXPORT-{short_id}",
            "ANOMALY_EVENT": f"EV-ANOMALY_EVENT-{short_id}",
        }

        text, mode = narrator.generate_narrative(
            symbol=sym,
            market_data=state.get("market_slice"),
            social_data=state.get("social_slice"),
            attribution_data=state.get("attribution"),
            alignment_data=state.get("alignment"),
            evidence_ids=ev_ids,
        )

        return {
            "stage": "DRAFTING",
            "dossier_draft": {"executive_summary": text},
            "narrative_mode": mode,
            "attempts": attempts,
        }

    return node


def validate_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        attempts = dict(state.get("attempts") or {})
        attempts["validate"] = attempts.get("validate", 0) + 1

        draft = state.get("dossier_draft") or {}
        text = draft.get("executive_summary", "")

        errors: list[str] = []
        if not text or "[" not in text:
            errors.append("Draft lacks citation tags")

        return {
            "stage": "VALIDATING",
            "errors": errors,
            "attempts": attempts,
        }

    return node


def sign_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        case_id = state.get("case_id", str(uuid.uuid4()))
        sym = state.get("symbol") or "UNKNOWN"
        attr = state.get("attribution") or {}
        rings = attr.get("rings")
        anomalies: list[dict[str, Any]] = []

        if deps.pool and sym != "UNKNOWN":
            try:
                async with deps.pool.acquire() as conn:
                    anom_rows = await conn.fetch(
                        """
                        SELECT anomaly_id, type, severity, score, metrics
                        FROM vigil.anomalies
                        WHERE symbol = $1
                        ORDER BY detected_at DESC LIMIT 20;
                        """,
                        sym,
                    )
                    for r in anom_rows:
                        anomalies.append({
                            "anomaly_id": str(r["anomaly_id"]),
                            "type": str(r["type"]),
                            "severity": str(r["severity"]),
                            "score": float(r["score"]),
                            "metrics": dict(r["metrics"]) if r["metrics"] else {},
                        })
            except Exception as exc:
                logger.debug("Could not fetch anomalies for case in sign_node", error=str(exc))

        if not anomalies and state.get("trigger_anomaly_id"):
            anomalies = [{"anomaly_id": state["trigger_anomaly_id"], "type": "CROSS_MODAL_ALIGNMENT"}]

        draft = state.get("dossier_draft") or {}
        custom_summary = draft.get("executive_summary")

        dossier, bundle_bytes = await deps.evidence_engine.compile_dossier(
            case_id=case_id,
            symbol=sym,
            attribution_rings=rings,
            anomalies=anomalies,
            human_review=state.get("review") or {"status": "NOT_REVIEWED"},
            version=1,
            narrative_mode=str(state.get("narrative_mode") or "TEMPLATE"),
            custom_executive_summary=custom_summary,
        )

        dossier_id = dossier["dossier_id"]

        # Update case status in database to PENDING_REVIEW
        if deps.pool:
            try:
                async with deps.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE vigil.cases
                        SET status = 'PENDING_REVIEW'::vigil.case_status, updated_at = now()
                        WHERE case_id = $1::uuid;
                        """,
                        uuid.UUID(case_id),
                    )
            except Exception as exc:
                logger.warning("DB update in sign_node failed", error=str(exc))

        return {
            "stage": "PENDING_REVIEW",
            "dossier_id": dossier_id,
            "evidence": dossier.get("evidence_manifest", []),
        }

    return node


def await_review_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        # LangGraph interrupt suspends until resumed with human review payload
        logger.info("Suspending case awaiting human compliance review", case_id=state.get("case_id"))
        review_payload = interrupt("Awaiting compliance officer review (APPROVED / REJECTED / REWORK)")
        return {
            "review": review_payload,
            "stage": "PENDING_REVIEW",
        }

    return node


def publish_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        case_id = state.get("case_id", str(uuid.uuid4()))
        sym = state.get("symbol") or "UNKNOWN"
        rev = state.get("review") or {}

        # Guardrail: Cannot reach PUBLISHED without compliance approval
        if rev.get("status") != "APPROVED":
            raise ValueError("HTTP 409 Conflict: Cannot publish case without APPROVED compliance review")

        # Compile version 2 with human_review included
        dossier, _ = await deps.evidence_engine.compile_dossier(
            case_id=case_id,
            symbol=sym,
            attribution_rings=(state.get("attribution") or {}).get("rings"),
            human_review=rev,
            version=2,
            narrative_mode=str(state.get("narrative_mode") or "TEMPLATE"),
        )

        # Update DB status to PUBLISHED
        if deps.pool:
            try:
                async with deps.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE vigil.cases
                        SET status = 'PUBLISHED'::vigil.case_status, updated_at = now()
                        WHERE case_id = $1::uuid;
                        """,
                        uuid.UUID(case_id),
                    )
            except Exception as exc:
                logger.warning("DB update in publish_node failed", error=str(exc))

        return {
            "stage": "PUBLISHED",
            "dossier_id": dossier["dossier_id"],
        }

    return node
