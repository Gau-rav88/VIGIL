from typing import Any, Literal

from pydantic import BaseModel, Field


class Party(BaseModel):
    account_id: str = Field(..., pattern=r"^[A-Za-z0-9_-]{22,64}$")
    broker_id: str = Field(..., min_length=1, max_length=32)
    gateway_id: str | None = Field(default=None, max_length=64)
    order_id: str | None = Field(default=None, max_length=64)
    device_fp: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{22,64}$")
    ip_hash: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{22,64}$")
    asn: int | None = Field(default=None, ge=0)
    api_client_id: str | None = Field(default=None, max_length=64)
    order_to_ack_us: int | None = Field(default=None, ge=0)


class TradeTick(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    event_id: str
    exchange: Literal["NSE", "BSE", "NASDAQ", "NYSE", "SYNTH"]
    symbol: str = Field(..., pattern=r"^[A-Z0-9&._-]{1,24}$")
    isin: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    trade_id: str = Field(..., max_length=64)
    seq: int = Field(..., ge=0)
    ts_exchange: str
    ts_received: str | None = None
    ts_ingest: str | None = None
    price: str = Field(..., pattern=r"^\d+(\.\d{1,8})?$")
    qty: int = Field(..., ge=1)
    aggressor_side: Literal["BUY", "SELL", "UNKNOWN"]
    buyer: Party
    seller: Party
    market_segment: Literal["CASH", "FNO", "SME", "OTHER"] | None = None
    is_synthetic: bool
    scenario_label: str | None = None
    ingest_latency_us: int | None = Field(default=None, ge=0)


class L2Snapshot(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    event_id: str
    exchange: Literal["NSE", "BSE", "NASDAQ", "NYSE", "SYNTH"]
    symbol: str = Field(..., pattern=r"^[A-Z0-9&._-]{1,24}$")
    seq: int = Field(..., ge=0)
    ts_exchange: str
    ts_ingest: str | None = None
    depth_levels: int = Field(..., ge=5, le=50)
    bids: list[list[Any]] = Field(..., max_length=50)
    asks: list[list[Any]] = Field(..., max_length=50)
    is_snapshot: bool = True
    is_synthetic: bool


class L3OrderEvent(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    event_id: str
    exchange: Literal["NSE", "BSE", "NASDAQ", "NYSE", "SYNTH"]
    symbol: str = Field(..., pattern=r"^[A-Z0-9&._-]{1,24}$")
    seq: int = Field(..., ge=0)
    ts_exchange: str
    ts_ingest: str | None = None
    order_id: str = Field(..., max_length=64)
    orig_order_id: str | None = None
    action: Literal["NEW", "MODIFY", "CANCEL", "TRADE"]
    side: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT", "MARKET", "IOC", "FOK"] | None = None
    price: str | None = Field(default=None, pattern=r"^\d+(\.\d{1,8})?$")
    qty: int | None = Field(default=None, ge=0)
    leaves_qty: int | None = Field(default=None, ge=0)
    account_id: str = Field(..., pattern=r"^[A-Za-z0-9_-]{22,64}$")
    broker_id: str = Field(..., max_length=32)
    gateway_id: str | None = Field(default=None, max_length=64)
    device_fp: str | None = None
    ip_hash: str | None = None
    asn: int | None = None
    api_client_id: str | None = None
    order_to_ack_us: int | None = Field(default=None, ge=0)
    is_synthetic: bool
