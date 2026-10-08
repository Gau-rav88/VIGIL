from typing import Literal, Any
from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    kind: Literal["trade_id", "order_id", "l2_seq", "social_message_id", "raw_object_uri", "anomaly_id"]
    ref: str
    sha256: str | None = None


class AnomalyEvent(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    anomaly_id: str
    type: Literal[
        "VOLUME_SPIKE",
        "SPREAD_WIDENING",
        "DEPTH_IMBALANCE",
        "SPOOFING_LAYERING",
        "WASH_CYCLE",
        "SYNCHRONIZED_ORDERS",
        "PRICE_JUMP",
        "HYPE_BURST",
        "NEAR_DUPLICATE_CAMPAIGN",
        "CROSS_MODAL_ALIGNMENT",
        "FINGERPRINT_CLUSTER",
        "CIRCULAR_RING",
        "COORDINATED_VOLUME_LOOP"
    ]
    source_agent: Literal["quant_telemetry", "social_intel", "attribution", "orchestrator"]
    symbol: str
    window_start: str
    window_end: str
    score: float = Field(..., ge=0, le=1)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    metrics: dict[str, Any]
    participants: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(..., min_length=1)
    detector_version: str
    config_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    detected_at: str
    case_id: str | None = None
