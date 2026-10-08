from datetime import datetime
from enum import Enum
from typing import TypedDict, Literal, Any
from pydantic import BaseModel


class CaseStage(str, Enum):
    OPENED = "OPENED"
    ENRICHING = "ENRICHING"
    ALIGNED = "ALIGNED"
    ATTRIBUTING = "ATTRIBUTING"
    ASSESSING = "ASSESSING"
    DRAFTING = "DRAFTING"
    VALIDATING = "VALIDATING"
    SIGNING = "SIGNING"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    REWORK = "REWORK"
    WATCHLIST = "WATCHLIST"
    CLOSED_NO_ACTION = "CLOSED_NO_ACTION"
    FAILED = "FAILED"


class WindowParams(BaseModel):
    start: datetime
    end: datetime
    widen_count: int = 0


class CaseTrigger(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    trigger_id: str
    symbol: str
    exchange: str = "SYNTH"
    anomaly_id: str
    window_start: datetime
    window_end: datetime
    score: float
    detected_at: datetime


class CaseEvent(BaseModel):
    case_id: str
    actor: str
    kind: str
    payload: dict[str, Any]
    ts: datetime


class CaseState(TypedDict, total=False):
    case_id: str
    symbol: str
    exchange: str
    stage: CaseStage
    trigger_anomaly_id: str
    window: WindowParams
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
