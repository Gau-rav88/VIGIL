from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterator, Optional

import numpy as np

from vigil_common.datasets import open_dataset
from vigil_common.models.market import Party, TradeTick


class DatasetTradeAdapter:
    """Maps arbitrary trade table records (CSV/Parquet/NDJSON) to TradeTick models.
    Applies a deterministic synthetic identity overlay when account data is absent (Guardrail G-6).
    """

    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)
        self.seq = 0
        self.brokers = ["BRK_ALPHA", "BRK_BETA", "BRK_GAMMA", "BRK_DELTA"]

    def _generate_synthetic_account(self) -> str:
        # Generates 22-character alphanumeric account identifier
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        chars = "".join(self.rng.choice(list(alphabet), size=18))
        return f"acc_{chars}"

    def to_trade_tick(self, record: Dict[str, Any], symbol: str = "ZENITHSME") -> TradeTick:
        self.seq += 1

        # Extract timestamps
        ts_val = record.get("ts_exchange") or record.get("timestamp") or record.get("ts") or record.get("time")
        if not ts_val:
            ts_iso = datetime.now(timezone.utc).isoformat()
        elif isinstance(ts_val, (int, float)):
            # Handle epoch timestamp in s or ms
            s = ts_val / 1000.0 if ts_val > 1e11 else ts_val
            ts_iso = datetime.fromtimestamp(s, tz=timezone.utc).isoformat()
        else:
            ts_iso = str(ts_val)

        # Extract prices and quantities
        raw_price = record.get("price") or record.get("p") or 100.0
        price_str = f"{float(raw_price):.2f}"
        qty = int(record.get("qty") or record.get("quantity") or record.get("size") or record.get("q") or 1)

        raw_side = str(record.get("side") or record.get("aggressor_side") or "BUY").upper()
        side = "BUY" if "B" in raw_side else ("SELL" if "S" in raw_side else "UNKNOWN")

        # Synthetic identity overlay if missing
        buyer_data = record.get("buyer") or {}
        seller_data = record.get("seller") or {}

        is_synthetic = bool(record.get("is_synthetic", False))
        if not buyer_data.get("account_id") or not seller_data.get("account_id"):
            is_synthetic = True
            buyer_acc = buyer_data.get("account_id") or self._generate_synthetic_account()
            seller_acc = seller_data.get("account_id") or self._generate_synthetic_account()
            buyer_party = Party(
                account_id=buyer_acc,
                broker_id=buyer_data.get("broker_id") or str(self.rng.choice(self.brokers)),
            )
            seller_party = Party(
                account_id=seller_acc,
                broker_id=seller_data.get("broker_id") or str(self.rng.choice(self.brokers)),
            )
        else:
            buyer_party = Party(**buyer_data)
            seller_party = Party(**seller_data)

        trade_id = str(record.get("trade_id") or f"T-{self.seq:09d}")
        sym = str(record.get("symbol") or symbol).upper()

        return TradeTick(
            schema_version="1.0.0",
            event_id=f"evt_replay_{self.seq:08d}",
            exchange="NSE",
            symbol=sym,
            trade_id=trade_id,
            seq=self.seq,
            ts_exchange=ts_iso,
            price=price_str,
            qty=qty,
            aggressor_side=side,  # type: ignore[arg-type]
            buyer=buyer_party,
            seller=seller_party,
            is_synthetic=is_synthetic,
        )


class FileReplayAdapter:
    """Streams records from datasets at accelerated or real-time inter-arrival speeds."""

    def __init__(self, dataset_name: str, speed: float = 1.0, data_dir: Optional[Path] = None) -> None:
        self.dataset_name = dataset_name
        self.speed = max(0.1, speed)
        self.data_dir = data_dir
        self.adapter = DatasetTradeAdapter()

    def iter_trade_ticks(self, symbol: str = "ZENITHSME") -> Iterator[TradeTick]:
        records = open_dataset(self.dataset_name, data_dir=self.data_dir)
        for rec in records:
            yield self.adapter.to_trade_tick(rec, symbol=symbol)

    async def aiter_trade_ticks(self, symbol: str = "ZENITHSME", delay_ms: float = 1.0) -> AsyncIterator[TradeTick]:
        delay_s = max(0.0001, (delay_ms / 1000.0) / self.speed)
        for tick in self.iter_trade_ticks(symbol=symbol):
            yield tick
            await asyncio.sleep(delay_s)
