from typing import Literal, Any
from pydantic import BaseModel, Field


class DossierSubject(BaseModel):
    symbol: str
    exchange: str
    isin: str | None = None
    window_start: str
    window_end: str
    manipulation_types: list[Literal[
        "PUMP_AND_DUMP",
        "WASH_TRADING",
        "CIRCULAR_TRADING",
        "SPOOFING_LAYERING",
        "COORDINATED_LIQUIDITY_SQUEEZE"
    ]] = Field(..., min_length=1)


class ExecutiveSummary(BaseModel):
    text: str = Field(..., max_length=4000)
    citations: list[str] = Field(..., min_length=1)


class TimelineEntry(BaseModel):
    ts: str
    track: Literal["SOCIAL", "MARKET", "GRAPH", "SYSTEM"]
    description: str = Field(..., max_length=1000)
    evidence_ids: list[str] = Field(..., min_length=1)


class MarketEvidence(BaseModel):
    total_volume: int
    suspect_volume: int
    suspect_volume_ratio: float = Field(..., ge=0, le=1)
    price_move_pct: float
    anomalies: list[str]


class SocialAlignment(BaseModel):
    best_lag_s: float | None = None
    xcorr_peak: float | None = None
    p_value: float | None = None


class SocialEvidence(BaseModel):
    channels: list[str]
    message_count: int
    hype_peak: float
    cta_breakdown: dict[str, int]
    near_duplicate_campaigns: int
    alignment: SocialAlignment | None = None


class RingAttribution(BaseModel):
    ring_id: str
    entity_id: str
    ring_score: float = Field(..., ge=0, le=1)
    accounts: list[str] = Field(..., min_length=2)
    methods: list[Literal[
        "SHARED_DEVICE",
        "SHARED_NETWORK",
        "SHARED_KYC",
        "LATENCY_SIGNATURE",
        "BROKER_PATHWAY",
        "CIRCULAR_CYCLE",
        "SYNCHRONIZED_ORDERS",
        "REACTION_LATENCY"
    ]]
    cycle_count: int
    net_volume: int
    evidence_ids: list[str] = Field(..., min_length=1)


class LeadAttribution(BaseModel):
    account_id: str
    confidence: float
    note: str | None = None


class AttributionFinding(BaseModel):
    rings: list[RingAttribution]
    leads: list[LeadAttribution]


class ViolatedClause(BaseModel):
    regime: Literal["SEBI", "SEC"]
    clause_id: str
    title: str
    finding_types: list[str]
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    legal_review_required: bool


class ConfidenceScore(BaseModel):
    overall: float = Field(..., ge=0, le=1)
    completeness: float = Field(..., ge=0, le=1)
    components: dict[str, float]


class EvidenceManifestItem(BaseModel):
    evidence_id: str
    type: Literal[
        "TRADE_SLICE",
        "L2_SLICE",
        "L3_SLICE",
        "SOCIAL_SLICE",
        "GRAPH_EXPORT",
        "CHART_IMAGE",
        "ANOMALY_EVENT",
        "LLM_TRACE",
        "CONFIG_SNAPSHOT"
    ]
    sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    uri: str
    bytes: int
    captured_at: str


class LedgerAnchor(BaseModel):
    entry_id: int
    entry_hash: str
    prev_entry_hash: str
    tsa_token_b64: str | None = None


class DossierSignature(BaseModel):
    alg: Literal["Ed25519"] = "Ed25519"
    key_id: str
    canonicalization: Literal["RFC8785-JCS"] = "RFC8785-JCS"
    digest_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    value_b64: str
    signed_at: str


class HumanReview(BaseModel):
    status: Literal["NOT_REVIEWED", "APPROVED", "REJECTED", "REWORK"]
    reviewer_id: str | None = None
    reviewed_at: str | None = None
    comment: str | None = None


class ForensicDossier(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    dossier_id: str
    version: int = Field(..., ge=1)
    supersedes: str | None = None
    case_id: str
    generated_at: str
    jurisdiction: Literal["SEBI_IN", "SEC_US", "GENERIC"]
    subject: DossierSubject
    executive_summary: ExecutiveSummary
    timeline: list[TimelineEntry] = Field(..., min_length=1)
    market_evidence: MarketEvidence
    social_evidence: SocialEvidence
    attribution: AttributionFinding
    violated_clauses: list[ViolatedClause]
    confidence: ConfidenceScore
    limitations: list[str] = Field(..., min_length=1)
    evidence_manifest: list[EvidenceManifestItem] = Field(..., min_length=1)
    merkle_root: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    ledger_anchor: LedgerAnchor
    signature: DossierSignature
    human_review: HumanReview
