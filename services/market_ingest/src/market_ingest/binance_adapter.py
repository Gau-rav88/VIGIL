from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
from typing import Any, AsyncGenerator

import websockets
from vigil_common.logging import get_logger
from vigil_common.models.market import Party, TradeTick

logger = get_logger("binance_adapter")


class BinanceMarketAdapter:
    """
    Real-world Binance public WebSocket connector.
    Connects to live Binance WebSocket streams for specified symbols (e.g. BTCUSDT, ETHUSDT, SOLUSDT).
    Streams live trades and L2 depth directly into VIGIL format.
    Requires ZERO API keys or credentials ($0.00 cost).
    """

    def __init__(self, symbols: list[str] | None = None) -> None:
        self.symbols = [s.strip().upper() for s in (symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"])]
        self.running = False
        self.seq_counters: dict[str, int] = {s: 0 for s in self.symbols}

    def _build_stream_url(self) -> str:
        streams = []
        for s in self.symbols:
            s_lower = s.lower()
            streams.append(f"{s_lower}@trade")
            streams.append(f"{s_lower}@depth20@100ms")
        stream_path = "/".join(streams)
        return f"wss://stream.binance.com:9443/stream?streams={stream_path}"

    async def stream(self) -> AsyncGenerator[str, None]:
        self.running = True
        url = self._build_stream_url()
        reconnect_delay = 1.0

        while self.running:
            try:
                logger.info("Connecting to Binance live WebSocket feed...", url=url, symbols=self.symbols)
                async with websockets.connect(url, max_size=10 * 1024 * 1024) as ws:
                    reconnect_delay = 1.0
                    logger.info("Connected to Binance live market stream!")

                    while self.running:
                        raw_msg = await ws.recv()
                        parsed = self._normalize_frame(raw_msg)
                        if parsed:
                            yield json.dumps(parsed)

            except (websockets.ConnectionClosed, OSError) as exc:
                if not self.running:
                    break
                logger.warning("Binance WebSocket disconnected, retrying...", error=str(exc), delay=reconnect_delay)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 10.0)
            except Exception as exc:
                if not self.running:
                    break
                logger.error("Unexpected error in Binance stream loop", error=str(exc))
                await asyncio.sleep(1.0)

    def _normalize_frame(self, raw_msg: str | bytes) -> dict[str, Any] | None:
        try:
            wrapper = json.loads(raw_msg)
            stream_name: str = wrapper.get("stream", "")
            data: dict[str, Any] = wrapper.get("data", {})
            if not stream_name or not data:
                return None

            if stream_name.endswith("@trade"):
                # Binance trade event
                symbol = data.get("s", "UNKNOWN").upper()
                trade_id = data.get("t", 0)
                price_str = str(data.get("p", "0"))
                qty_float = float(data.get("q", 0.0))
                trade_time_ms = data.get("T", 0)
                is_buyer_maker = bool(data.get("m", False))
                buyer_order_id = str(data.get("b", 0))
                seller_order_id = str(data.get("a", 0))

                buyer_hash = hashlib.sha256(f"BINANCE|{symbol}|{trade_id}|BUY".encode()).hexdigest()[:24]
                seller_hash = hashlib.sha256(f"BINANCE|{symbol}|{trade_id}|SELL".encode()).hexdigest()[:24]
                buyer_acc = f"anon_{buyer_hash}"
                seller_acc = f"anon_{seller_hash}"

                self.seq_counters[symbol] = self.seq_counters.get(symbol, 0) + 1
                seq = self.seq_counters[symbol]

                ts_exch = datetime.datetime.fromtimestamp(
                    trade_time_ms / 1000.0 if trade_time_ms else datetime.datetime.now(datetime.timezone.utc).timestamp(),
                    datetime.timezone.utc,
                ).isoformat()

                tick = TradeTick(
                    schema_version="1.0.0",
                    event_id=f"binance-trade-{trade_id}",
                    exchange="BINANCE",
                    symbol=symbol,
                    trade_id=str(trade_id),
                    seq=seq,
                    ts_exchange=ts_exch,
                    price=price_str,
                    qty=max(1, int(qty_float * 10000)),
                    aggressor_side="SELL" if is_buyer_maker else "BUY",
                    buyer=Party(
                        account_id=buyer_acc,
                        broker_id="BINANCE",
                        order_id=buyer_order_id,
                    ),
                    seller=Party(
                        account_id=seller_acc,
                        broker_id="BINANCE",
                        order_id=seller_order_id,
                    ),
                    market_segment="CASH",
                    is_synthetic=True,
                )

                return {
                    "kind": "trade",
                    "data": tick.model_dump(mode="json"),
                }

            elif "@depth" in stream_name:
                # Binance L2 depth snapshot
                symbol = stream_name.split("@")[0].upper()
                last_update_id = data.get("lastUpdateId", 0)
                raw_bids = data.get("bids", [])
                raw_asks = data.get("asks", [])

                bids = [[float(p), float(q)] for p, q in raw_bids[:20]]
                asks = [[float(p), float(q)] for p, q in raw_asks[:20]]

                self.seq_counters[symbol] = self.seq_counters.get(symbol, 0) + 1
                seq = self.seq_counters[symbol]

                return {
                    "kind": "l2",
                    "data": {
                        "schema_version": "1.0.0",
                        "event_id": f"binance-depth-{last_update_id}-{seq}",
                        "exchange": "BINANCE",
                        "symbol": symbol,
                        "seq": seq,
                        "ts_exchange": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "depth_levels": max(5, min(len(bids), 50)),
                        "bids": bids,
                        "asks": asks,
                        "is_snapshot": True,
                        "is_synthetic": False,
                    },
                }

            return None

        except Exception as exc:
            logger.debug("Failed to normalize Binance frame", error=str(exc))
            return None

    def stop(self) -> None:
        self.running = False
