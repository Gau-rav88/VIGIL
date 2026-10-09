from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class AgentMessage(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    msg_id: UUID
    correlation_id: UUID
    case_id: UUID | None
    sender: Literal["orchestrator", "quant_telemetry", "social_intel", "attribution", "alignment", "evidence_engine", "api"]
    recipient: str
    type: Literal[
        "REQUEST_MARKET_SLICE", "MARKET_SLICE_RESULT",
        "REQUEST_SOCIAL_SLICE", "SOCIAL_SLICE_RESULT",
        "REQUEST_ALIGNMENT", "ALIGNMENT_RESULT",
        "REQUEST_ATTRIBUTION", "ATTRIBUTION_RESULT",
        "DIRECTIVE", "ERROR"
    ]
    payload: dict[str, Any]
    ts: datetime
    ttl_s: int = 120
    attempt: int = 1
    idempotency_key: str
