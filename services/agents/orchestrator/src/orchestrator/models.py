from __future__ import annotations

import datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

CaseStage = Literal[
    "OPENED",
    "ENRICHING",
    "ALIGNED",
    "WATCHLIST",
    "ATTRIBUTING",
    "ASSESSING",
    "DRAFTING",
    "VALIDATING",
    "SIGNING",
    "PENDING_REVIEW",
    "APPROVED",
    "REJECTED",
    "REWORK",
    "PUBLISHED",
    "CLOSED_NO_ACTION",
    "FAILED",
]


class WindowParams(BaseModel):
    start: str
    end: str
    widen_count: int = 0


class AgentMessage(BaseModel):
    version: str = "1.0.0"
    message_id: str
    correlation_id: str
    sender: str
    recipient: str
    command: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class CaseState(TypedDict, total=False):
    case_id: str
    symbol: str
    exchange: str
    stage: CaseStage
    trigger_anomaly_id: str
    window: dict[str, Any]
    market_slice: dict[str, Any] | None
    social_slice: dict[str, Any] | None
    alignment: dict[str, Any] | None
    attribution: dict[str, Any] | None
    anomalies: list[str]
    evidence: list[dict[str, Any]]
    confidence: dict[str, Any] | None
    clauses: list[dict[str, Any]]
    dossier_draft: dict[str, Any] | None
    dossier_id: str | None
    narrative_mode: Literal["LLM", "TEMPLATE"] | None
    directives: list[dict[str, Any]]
    attempts: dict[str, int]
    flags: list[str]
    errors: list[dict[str, Any]]
    review: dict[str, Any] | None
