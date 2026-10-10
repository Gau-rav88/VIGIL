from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class LinkMethod(str, Enum):
    SHARED_KYC = "SHARED_KYC"
    SHARED_DEVICE = "SHARED_DEVICE"
    CIRCULAR_CYCLE = "CIRCULAR_CYCLE"
    SYNCHRONIZED_ORDERS = "SYNCHRONIZED_ORDERS"
    SHARED_NETWORK = "SHARED_NETWORK"
    LATENCY_SIGNATURE = "LATENCY_SIGNATURE"
    REACTION_LATENCY = "REACTION_LATENCY"
    BROKER_PATHWAY = "BROKER_PATHWAY"


class MethodScore(BaseModel):
    method: LinkMethod
    weight: float = Field(..., ge=0.0, le=1.0)
    strength: float = Field(..., ge=0.0, le=1.0)
    details: dict[str, Any] = Field(default_factory=dict)


class AccountPairLink(BaseModel):
    source_account: str
    target_account: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    methods: list[LinkMethod] = Field(default_factory=list)
    method_scores: list[MethodScore] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    is_finding: bool = False
    is_vetoed: bool = False


class EntityCluster(BaseModel):
    entity_id: str
    case_id: str | None = None
    accounts: list[str] = Field(default_factory=list)
    ring_score: float = Field(..., ge=0.0, le=1.0)
    volume_share: float = Field(default=0.0, ge=0.0, le=1.0)
    brokers: list[str] = Field(default_factory=list)
    shared_devices: list[str] = Field(default_factory=list)
    shared_asns: list[int] = Field(default_factory=list)
    cycles_count: int = 0
    findings_links: list[AccountPairLink] = Field(default_factory=list)
    leads_links: list[AccountPairLink] = Field(default_factory=list)


class CyclePath(BaseModel):
    accounts: list[str]
    length: int
    lead_qty: float
    cycle_volume: float
    start_ms: int
    end_ms: int
    evidence_trade_ids: list[str] = Field(default_factory=list)


class GraphUpdate(BaseModel):
    update_type: Literal[
        "TRADE",
        "ORDER_L3",
        "SYNC_PAIR",
        "DEVICE_FP",
        "NETWORK_FP",
        "BROKER_ROUTE",
        "SOCIAL_REACTION",
        "FEEDBACK_VETO"
    ]
    symbol: str
    timestamp_ms: int
    payload: dict[str, Any]


class CytoscapeNodeData(BaseModel):
    id: str
    label: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class CytoscapeNode(BaseModel):
    data: CytoscapeNodeData


class CytoscapeEdgeData(BaseModel):
    id: str
    source: str
    target: str
    type: str
    confidence: float | None = None
    weight: float | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class CytoscapeEdge(BaseModel):
    data: CytoscapeEdgeData


class CytoscapeGraph(BaseModel):
    nodes: list[CytoscapeNode] = Field(default_factory=list)
    edges: list[CytoscapeEdge] = Field(default_factory=list)


class LinkFeedbackAction(str, Enum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"


class LinkFeedback(BaseModel):
    case_id: str
    source_account: str
    target_account: str
    verdict: LinkFeedbackAction
    comment: str | None = None
    actor: str = "investigator"
    timestamp_iso: str
