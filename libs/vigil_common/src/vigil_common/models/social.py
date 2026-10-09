from typing import Literal

from pydantic import BaseModel, Field


class SocialMessage(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    event_id: str
    platform: Literal["telegram", "discord", "reddit", "x", "stocktwits", "forum"]
    channel_id: str = Field(..., max_length=96)
    channel_name: str | None = Field(default=None, max_length=256)
    channel_visibility: Literal["public", "lawful_access"]
    channel_member_count: int | None = Field(default=None, ge=0)
    message_id: str = Field(..., max_length=96)
    author_id: str = Field(..., pattern=r"^[A-Za-z0-9_-]{22,64}$")
    author_display_hash: str | None = None
    ts_posted: str
    ts_ingest: str | None = None
    text: str = Field(..., max_length=8192)
    lang: str | None = Field(default=None, pattern=r"^[a-z]{2,3}(-[A-Za-z]+)?$")
    reply_to_message_id: str | None = None
    forwarded_from_channel_id: str | None = None
    views: int | None = Field(default=None, ge=0)
    reactions: int | None = Field(default=None, ge=0)
    urls: list[str] = Field(default_factory=list, max_length=20)
    media_sha256: list[str] = Field(default_factory=list, max_length=10)
    raw_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    is_synthetic: bool
    scenario_label: str | None = None


class ParserMetadata(BaseModel):
    mode: Literal["LLM", "FALLBACK_RULES"]
    version: str
    llm_model: str | None = None
    prompt_sha256: str | None = None
    response_sha256: str | None = None


class SocialSignal(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    signal_id: str
    message_event_id: str
    platform: str
    channel_id: str
    author_id: str
    ts_posted: str
    ts_processed: str | None = None
    ticker: str = Field(..., pattern=r"^[A-Z0-9&._-]{1,24}$")
    ticker_confidence: float = Field(..., ge=0, le=1)
    mention_type: Literal["CASHTAG", "SYMBOL", "COMPANY_NAME", "ALIAS"] | None = None
    cta_class: Literal["BUY_CALL", "HOLD_PUMP", "TARGET_PRICE", "EXIT_SIGNAL", "COORDINATION_TIMING", "NEUTRAL"]
    cta_confidence: float | None = Field(default=None, ge=0, le=1)
    target_price: str | None = Field(default=None, pattern=r"^\d+(\.\d{1,8})?$")
    scheduled_action_time: str | None = None
    urgency: float = Field(..., ge=0, le=1)
    sentiment: float | None = Field(default=None, ge=-1, le=1)
    near_dup_cluster_id: str | None = None
    forward_cascade_depth: int = Field(default=0, ge=0)
    raw_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    parser: ParserMetadata
