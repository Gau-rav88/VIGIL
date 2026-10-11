from __future__ import annotations

import asyncio
import base64
import collections
import datetime
import json
import os
import signal
import socket
import sys
from pathlib import Path

from dotenv import load_dotenv

# Auto-add vigil_common and services to sys.path if missing
_cur = Path(__file__).resolve()
_root = _cur.parents[4] if len(_cur.parents) >= 5 else Path.cwd()
for _p in [
    _root / "libs" / "vigil_common" / "src",
    _root / "services" / "market_ingest" / "src",
]:
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

if (_root / ".env").exists():
    load_dotenv(_root / ".env")
else:
    load_dotenv()

import fastjsonschema
import websockets
from aiokafka import AIOKafkaProducer
from vigil_common.logging import get_logger, setup_logging

from market_ingest.binance_adapter import BinanceMarketAdapter

logger = get_logger("market_ingest")


def resolve_kafka_bootstrap(bootstrap: str) -> str:
    host, _, _ = bootstrap.partition(":")
    if host == "redpanda":
        try:
            socket.gethostbyname("redpanda")
        except socket.gaierror:
            return f"localhost:{os.getenv('KAFKA_EXTERNAL_PORT', '19092')}"
    return bootstrap


def find_schemas_dir() -> Path:
    candidates = [
        Path("/app/libs/vigil_common/schemas"),
        Path(__file__).resolve().parents[4] / "libs" / "vigil_common" / "schemas",
        Path.cwd() / "libs" / "vigil_common" / "schemas",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return Path("libs/vigil_common/schemas")


class MarketIngester:
    def __init__(self) -> None:
        self.adapter_type = os.getenv("MARKET_ADAPTER", "websocket").lower()
        self.binance_symbols = [s.strip() for s in os.getenv("BINANCE_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",") if s.strip()]
        self.ws_url = os.getenv("MARKET_WS_URL", "ws://simulator:8090/ws/market")
        self.kafka_bootstrap = resolve_kafka_bootstrap(os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092"))
        self.keep_scenario_labels = os.getenv("KEEP_SCENARIO_LABELS", "false").lower() == "true"
        self.high_watermark = int(os.getenv("INGEST_QUEUE_HIGH_WATERMARK", "50000"))
        self.producer: AIOKafkaProducer | None = None
        self.running = False
        self.binance_adapter: BinanceMarketAdapter | None = None

        # Deduplication
        self.seen_events: collections.deque[str] = collections.deque(maxlen=100000)
        self.seen_set: set[str] = set()

        # Sequence gap tracking: symbol -> last_seq
        self.last_seq: dict[str, int] = {}

        # Stats & metrics
        self.stats = {"trades": 0, "l2": 0, "l3": 0, "dupes": 0, "errors": 0, "dlq": 0, "seq_gaps": 0, "shed": 0}

        # Load compiled schema validators
        self._load_validators()

    def _load_validators(self) -> None:
        schemas_dir = find_schemas_dir()
        try:
            trade_schema = json.loads((schemas_dir / "trade_tick.schema.json").read_text(encoding="utf-8"))
            l2_schema = json.loads((schemas_dir / "l2_snapshot.schema.json").read_text(encoding="utf-8"))
            l3_schema = json.loads((schemas_dir / "l3_order_event.schema.json").read_text(encoding="utf-8"))

            self.val_trade = fastjsonschema.compile(trade_schema)
            self.val_l2 = fastjsonschema.compile(l2_schema)
            self.val_l3 = fastjsonschema.compile(l3_schema)
        except Exception as exc:
            logger.warning("Could not pre-compile all fastjsonschema validators", error=str(exc))
            self.val_trade = lambda x: x
            self.val_l2 = lambda x: x
            self.val_l3 = lambda x: x

    def _is_duplicate(self, event_id: str) -> bool:
        if event_id in self.seen_set:
            return True
        if len(self.seen_events) >= 100000:
            oldest = self.seen_events.popleft()
            self.seen_set.discard(oldest)
        self.seen_events.append(event_id)
        self.seen_set.add(event_id)
        return False

    async def start(self) -> None:
        self.running = True
        logger.info(
            "Starting market_ingest",
            ws_url=self.ws_url,
            kafka_bootstrap=self.kafka_bootstrap,
            keep_scenario_labels=self.keep_scenario_labels,
        )

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            acks=1,
            linger_ms=5,
        )
        await self.producer.start()
        logger.info("Kafka producer connected to Redpanda")

        if self.adapter_type == "binance":
            logger.info("Using Binance live market adapter", symbols=self.binance_symbols)
            self.binance_adapter = BinanceMarketAdapter(self.binance_symbols)
            async for msg in self.binance_adapter.stream():
                if not self.running:
                    break
                await self._process_message(msg)
        else:
            reconnect_delay = 1.0
            while self.running:
                try:
                    logger.info("Connecting to market simulator WebSocket...", url=self.ws_url)
                    async with websockets.connect(self.ws_url, max_size=10 * 1024 * 1024) as ws:
                        reconnect_delay = 1.0
                        logger.info("Connected to market simulator stream")
                        while self.running:
                            raw_frame = await ws.recv()
                            await self._process_message(raw_frame)

                except (websockets.ConnectionClosed, OSError) as exc:
                    if not self.running:
                        break
                    logger.warning("WebSocket disconnected, retrying...", error=str(exc), delay=reconnect_delay)
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, 10.0)
                except Exception as exc:
                    if not self.running:
                        break
                    logger.error("Unexpected error in market ingest loop", error=str(exc))
                    await asyncio.sleep(1.0)

    async def _send_dlq(self, raw_msg: str | bytes, error_msg: str) -> None:
        self.stats["dlq"] += 1
        raw_bytes = raw_msg if isinstance(raw_msg, bytes) else raw_msg.encode("utf-8")
        dlq_event = {
            "original_b64": base64.b64encode(raw_bytes).decode("ascii"),
            "error": error_msg,
            "stage": "market_ingest",
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if self.producer:
            await self.producer.send(
                topic="dlq.market",
                value=json.dumps(dlq_event).encode("utf-8"),
            )

    async def _process_message(self, raw_msg: str | bytes) -> None:
        try:
            frame = json.loads(raw_msg)
            kind = frame.get("kind")
            data = frame.get("data")
            if not kind or not data:
                await self._send_dlq(raw_msg, "Missing frame kind or data payload")
                return

            event_id = data.get("event_id")
            if event_id and self._is_duplicate(event_id):
                self.stats["dupes"] += 1
                return

            # Overload policy: if stats indicate high watermark, shed L2 deltas
            current_buffered = sum(self.stats.values())
            if current_buffered >= self.high_watermark and kind == "l2" and not data.get("is_snapshot"):
                self.stats["shed"] += 1
                return

            # Append ingest timestamp & microsecond latency (FR-MKT-05)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            data["ts_ingest"] = now_dt.isoformat()
            ts_exch_str = data.get("ts_exchange")
            if ts_exch_str:
                try:
                    ts_clean = ts_exch_str.replace("Z", "+00:00")
                    exch_dt = datetime.datetime.fromisoformat(ts_clean)
                    data["ingest_latency_us"] = max(0, int((now_dt - exch_dt).total_seconds() * 1_000_000))
                except Exception:
                    data["ingest_latency_us"] = 0

            # Strip scenario label if not in test mode
            if not self.keep_scenario_labels:
                data.pop("scenario_label", None)

            # JSON-Schema validation per event kind (FR-MKT-03)
            try:
                if kind == "trade":
                    self.val_trade(data)
                    topic = "market.trades.norm"
                    self.stats["trades"] += 1
                elif kind == "l2":
                    self.val_l2(data)
                    topic = "market.l2.norm"
                    self.stats["l2"] += 1
                elif kind == "l3":
                    self.val_l3(data)
                    topic = "market.l3.norm"
                    self.stats["l3"] += 1
                else:
                    await self._send_dlq(raw_msg, f"Unrecognized kind: {kind}")
                    return
            except Exception as schema_err:
                await self._send_dlq(raw_msg, f"Schema validation error: {schema_err}")
                return

            # Per-symbol sequence gap check (FR-MKT-04)
            symbol = data.get("symbol", "UNKNOWN")
            seq = data.get("seq")
            if seq is not None and isinstance(seq, int):
                last = self.last_seq.get(symbol)
                if last is not None and seq > last + 1:
                    self.stats["seq_gaps"] += 1
                    gap_event = {
                        "type": "SEQ_GAP",
                        "symbol": symbol,
                        "expected": last + 1,
                        "received": seq,
                        "ts": now_dt.isoformat(),
                    }
                    if self.producer:
                        await self.producer.send(
                            topic="health.events",
                            value=json.dumps(gap_event).encode("utf-8"),
                            key=symbol.encode("utf-8"),
                        )
                self.last_seq[symbol] = seq

            key = symbol.encode("utf-8")
            payload = json.dumps(data).encode("utf-8")

            if self.producer:
                await self.producer.send(topic=topic, value=payload, key=key)

            total = sum(self.stats.values())
            if total > 0 and total % 5000 == 0:
                logger.info("Market ingest progress", **self.stats)

        except json.JSONDecodeError as json_err:
            await self._send_dlq(raw_msg, f"JSON decode error: {json_err}")
        except Exception as exc:
            self.stats["errors"] += 1
            logger.error("Failed to process market message", error=str(exc))

    async def stop(self) -> None:
        self.running = False
        if self.binance_adapter:
            self.binance_adapter.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Market ingester stopped cleanly")


async def run() -> None:
    setup_logging()
    ingester = MarketIngester()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(ingester.start())

    await stop_event.wait()
    await ingester.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
