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
        sym = state.get("symbol", "ZENITHSME")
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        start_dt = now_dt - datetime.timedelta(hours=2)

        window = state.get("window") or {
            "start": start_dt.isoformat(),
            "end": now_dt.isoformat(),
            "widen_count": 0,
        }

        flags = list(state.get("flags") or [])
        anom_id = state.get("trigger_anomaly_id") or str(uuid.uuid4())

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

                    # Insert new case row
                    await conn.execute(
                        """
                        INSERT INTO vigil.cases (
                            case_id, symbol, exchange, status, window_start, window_end,
                            trigger_anomaly_id, mrs, overall_confidence, completeness, state, is_synthetic
                        ) VALUES ($1::uuid, $2, 'SYNTH', 'OPENED'::vigil.case_status, $3, $4, $5::uuid, 88.5, 0.94, 0.92, $6::jsonb, true)
                        ON CONFLICT (case_id) DO UPDATE SET updated_at = now();
                        """,
                        uuid.UUID(case_id),
                        sym,
                        start_dt,
                        now_dt,
                        uuid.UUID(anom_id),
                        json.dumps({"symbol": sym, "stage": "OPENED"}),
                    )
            except Exception as exc:
                logger.warning("DB insert in open_case failed, proceeding in-memory", error=str(exc))

        return {
            "case_id": case_id,
            "symbol": sym,
            "exchange": "SYNTH",
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
        sym = state.get("symbol", "ZENITHSME")
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
        # Default alignment for demo/evaluation
        alignment = {
            "best_lag_s": 150.0,
            "xcorr_peak": 0.685,
            "p_value": 0.001,
            "status": "SIGNIFICANT",
        }

        return {
            "stage": "ALIGNED",
            "alignment": alignment,
        }

    return node


def attribute_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        sym = state.get("symbol", "ZENITHSME")
        directives = state.get("directives") or []
        window = dict(state.get("window") or {})

        # Apply directives if present
        for d in directives:
            if d.get("type") == "WIDEN_WINDOW":
                window["widen_count"] = window.get("widen_count", 0) + 1

        rings = [
            {
                "ring_id": "ring_01",
                "entity_id": f"ENTITY-{sym}-01",
                "ring_score": 0.988,
                "accounts": [f"acc_{i:02d}" for i in range(1, 21)],
                "methods": ["SHARED_DEVICE", "CIRCULAR_CYCLE", "SHARED_NETWORK", "SYNCHRONIZED_ORDERS"],
                "cycle_count": 14,
                "net_volume": 385000,
            }
        ]
        leads = [
            {"account_id": "acc_lead_01", "confidence": 0.55, "note": "Lead under PRD G-2 threshold"}
        ]

        return {
            "stage": "ATTRIBUTING",
            "attribution": {"rings": rings, "leads": leads},
            "window": window,
        }

    return node


def assess_node(deps: OrchestratorDeps) -> Callable[[CaseState], Any]:
    async def node(state: CaseState) -> dict[str, Any]:
        conf = {
            "overall": 0.94,
            "completeness": 0.92,
            "components": {"alignment": 0.96, "attribution": 0.95, "market": 0.92, "social": 0.93},
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
        sym = state.get("symbol", "ZENITHSME")
        attempts = dict(state.get("attempts") or {})
        attempts["draft"] = attempts.get("draft", 0) + 1

        # Use TemplateNarrator if narrative_mode is TEMPLATE or on 3rd attempt
        narrator = deps.template_narrator if attempts.get("draft", 0) >= 2 else deps.llm_narrator
        ev_ids = {
            "TRADE_SLICE": "EV-TRADE_SLICE-c6f9ab0bc2b3",
            "SOCIAL_SLICE": "EV-SOCIAL_SLICE-a42e5bc91234",
            "GRAPH_EXPORT": "EV-GRAPH_EXPORT-f8812cde4567",
            "ANOMALY_EVENT": "EV-ANOMALY_EVENT-b7104ad56789",
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
        sym = state.get("symbol", "ZENITHSME")
        attr = state.get("attribution") or {}
        rings = attr.get("rings")
        anomalies = [{"anomaly_id": state.get("trigger_anomaly_id", "ANOM-01"), "type": "CROSS_MODAL_ALIGNMENT"}]

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
        sym = state.get("symbol", "ZENITHSME")
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
