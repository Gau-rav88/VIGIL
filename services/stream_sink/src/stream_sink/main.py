from __future__ import annotations

import asyncio
import base64
import datetime
import json
import os
import signal
from decimal import Decimal
from typing import Any

import asyncpg
import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from vigil_common.ids import to_event_uuid
from vigil_common.logging import get_logger, setup_logging
from vigil_common.network import resolve_db_dsn, resolve_kafka_bootstrap, resolve_redis_url
from vigil_common.topics import Topics

logger = get_logger("stream_sink")


def parse_dt(val: str | None) -> datetime.datetime:
    if not val:
        return datetime.datetime.now(datetime.timezone.utc)
    try:
        if val.endswith("Z"):
            val = val[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(val)
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


class StreamSink:
    def __init__(self) -> None:
        self.kafka_bootstrap = resolve_kafka_bootstrap(os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092"))
        self.pg_dsn = resolve_db_dsn(os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil"))
        self.redis_url = resolve_redis_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))

        self.pool: asyncpg.Pool | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.redis_client: aioredis.Redis | None = None
        self.running = False

        self.trade_batch: list[tuple[Any, ...]] = []
        self.l2_batch: list[tuple[Any, ...]] = []
        self.l2_metrics_batch: list[tuple[Any, ...]] = []
        self.l3_batch: list[tuple[Any, ...]] = []
        self.social_batch: list[tuple[Any, ...]] = []
        self.signals_batch: list[tuple[Any, ...]] = []
        self.hype_batch: list[tuple[Any, ...]] = []
        self.anomalies_batch: list[tuple[Any, ...]] = []

        self.watermarks: dict[str, float] = {}

        self.stats: dict[str, int] = {
            "inserted": 0,
            "dlq": 0,
            "retries": 0,
            "trades": 0,
            "l2": 0,
            "l2_metrics": 0,
            "l3": 0,
            "social": 0,
            "signals": 0,
            "hype": 0,
            "anomalies": 0,
        }

    async def start(self) -> None:
        self.running = True
        logger.info("Connecting to TimescaleDB...", dsn=self.pg_dsn)
        self.pool = await asyncpg.create_pool(
            dsn=self.pg_dsn,
            min_size=2,
            max_size=10,
        )
        logger.info("Connected to TimescaleDB")

        try:
            self.redis_client = aioredis.from_url(self.redis_url)
            logger.info("Connected to Redis for watermarks", url=self.redis_url)
        except Exception as exc:
            logger.warning("Could not connect to Redis for watermarks", error=str(exc))

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            acks=1,
        )
        await self.producer.start()
        logger.info("Kafka DLQ producer started")

        topics = [
            Topics.MARKET_TRADES_NORM,
            Topics.MARKET_L2_NORM,
            Topics.MARKET_L3_NORM,
            Topics.SOCIAL_MESSAGES_RAW,
            Topics.SOCIAL_SIGNALS_NORM,
            Topics.HYPE_SCORES_NORM,
            Topics.ANOMALY_MARKET,
            Topics.ANOMALY_SOCIAL,
            Topics.ANOMALY_FUSED,
        ]
        logger.info("Connecting to Redpanda consumer...", bootstrap=self.kafka_bootstrap, topics=topics)
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.kafka_bootstrap,
            group_id="stream_sink_workers",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        await self.consumer.start()
        logger.info("Kafka consumer started (auto_commit=False, offset_reset=earliest)")

        while self.running:
            try:
                msg_batch = await self.consumer.getmany(timeout_ms=500, max_records=200)
                if not msg_batch:
                    continue

                all_records: list[Any] = []
                for tp, records in msg_batch.items():
                    for record in records:
                        all_records.append(record)
                        success = await self._process_record(record.topic, record.value)
                        if not success:
                            # Record failed parsing/validation and went to DLQ
                            pass

                # Flush all buffered batches to TimescaleDB
                if (
                    self.trade_batch
                    or self.l2_batch
                    or self.l2_metrics_batch
                    or self.l3_batch
                    or self.social_batch
                    or self.signals_batch
                    or self.hype_batch
                    or self.anomalies_batch
                ):
                    flush_success = await self._flush_all_with_retry(all_records)
                    if flush_success or not self.running:
                        await self.consumer.commit()
                else:
                    await self.consumer.commit()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Consumer loop exception", error=str(exc))
                await asyncio.sleep(0.5)

    async def _send_to_dlq(self, value_bytes: bytes, topic: str, error: str, stage: str) -> None:
        self.stats["dlq"] += 1
        payload = {
            "original_b64": base64.b64encode(value_bytes).decode("ascii"),
            "topic": topic,
            "error": error,
            "stage": stage,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        logger.warning("Routing record to DLQ", topic=topic, stage=stage, error=error)
        if self.producer:
            try:
                await self.producer.send_and_wait(
                    topic=Topics.DLQ_SINK,
                    value=json.dumps(payload).encode("utf-8"),
                )
            except Exception as exc:
                logger.error("Failed to publish to DLQ", error=str(exc))

    async def _process_record(self, topic: str, value_bytes: bytes) -> bool:
        try:
            self._buffer_record(topic, value_bytes)
            return True
        except Exception as exc:
            await self._send_to_dlq(value_bytes, topic, error=str(exc), stage="parse")
            return False

    def _buffer_record(self, topic: str, value_bytes: bytes) -> None:
        data = json.loads(value_bytes)
        if not isinstance(data, dict):
            raise ValueError(f"Payload must be a JSON object, got {type(data).__name__}")

        if topic == Topics.MARKET_TRADES_NORM:
            buyer = data.get("buyer") or {}
            seller = data.get("seller") or {}
            raw_event_id = str(data.get("event_id", ""))
            exchange = data.get("exchange", "SYNTH")
            event_uuid = to_event_uuid(exchange, raw_event_id)

            ts_dt = parse_dt(data.get("ts_exchange"))
            symbol = data.get("symbol", "UNKNOWN")
            self.watermarks[symbol] = max(self.watermarks.get(symbol, 0.0), ts_dt.timestamp())

            trade_row = (
                ts_dt,
                event_uuid,
                exchange,
                symbol,
                str(data.get("trade_id", "T-0")),
                int(data.get("seq", 0)),
                Decimal(str(data.get("price", "0.0"))),
                int(data.get("qty", 0)),
                str(data.get("aggressor_side", "UNKNOWN")),
                buyer.get("account_id", ""),
                seller.get("account_id", ""),
                buyer.get("broker_id", ""),
                seller.get("broker_id", ""),
                buyer.get("gateway_id"),
                seller.get("gateway_id"),
                buyer.get("order_id"),
                seller.get("order_id"),
                buyer.get("device_fp"),
                seller.get("device_fp"),
                buyer.get("ip_hash"),
                seller.get("ip_hash"),
                buyer.get("asn"),
                seller.get("asn"),
                buyer.get("api_client_id"),
                seller.get("api_client_id"),
                buyer.get("order_to_ack_us"),
                seller.get("order_to_ack_us"),
                data.get("market_segment"),
                bool(data.get("is_synthetic", False)),
                parse_dt(data.get("ts_ingest")),
                raw_event_id,
            )
            self.trade_batch.append(trade_row)

        elif topic == Topics.MARKET_L3_NORM:
            raw_event_id = str(data.get("event_id", ""))
            exchange = data.get("exchange", "SYNTH")
            event_uuid = to_event_uuid(exchange, raw_event_id)

            ts_dt = parse_dt(data.get("ts_exchange"))
            symbol = data.get("symbol", "UNKNOWN")
            self.watermarks[symbol] = max(self.watermarks.get(symbol, 0.0), ts_dt.timestamp())

            l3_row = (
                ts_dt,
                event_uuid,
                exchange,
                symbol,
                int(data.get("seq", 0)),
                str(data.get("order_id", "")),
                data.get("orig_order_id"),
                str(data.get("action", "NEW")),
                str(data.get("side", "BUY")),
                data.get("order_type"),
                Decimal(str(data.get("price", "0.0"))) if data.get("price") is not None else None,
                int(data["qty"]) if data.get("qty") is not None else None,
                int(data["leaves_qty"]) if data.get("leaves_qty") is not None else None,
                data.get("account_id", ""),
                data.get("broker_id", ""),
                data.get("gateway_id"),
                data.get("device_fp"),
                data.get("ip_hash"),
                data.get("asn"),
                data.get("api_client_id"),
                data.get("order_to_ack_us"),
                bool(data.get("is_synthetic", False)),
                parse_dt(data.get("ts_ingest")),
                raw_event_id,
            )
            self.l3_batch.append(l3_row)

        elif topic == Topics.MARKET_L2_NORM:
            ts_dt = parse_dt(data.get("ts_exchange"))
            symbol = data.get("symbol", "UNKNOWN")
            self.watermarks[symbol] = max(self.watermarks.get(symbol, 0.0), ts_dt.timestamp())

            bids = data.get("bids", [])
            asks = data.get("asks", [])
            l2_row = (
                ts_dt,
                symbol,
                int(data.get("seq", 0)),
                data.get("exchange", "SYNTH"),
                json.dumps(bids),
                json.dumps(asks),
                int(data.get("depth_levels", 10)),
                bool(data.get("is_synthetic", False)),
            )
            self.l2_batch.append(l2_row)

            # Compute L2 metrics (1s / real snapshot resolution)
            best_bid = Decimal(str(bids[0][0])) if bids else None
            best_ask = Decimal(str(asks[0][0])) if asks else None
            rel_spread: float | None = None
            if best_bid is not None and best_ask is not None:
                mid = (float(best_bid) + float(best_ask)) / 2.0
                if mid > 0:
                    rel_spread = float(best_ask - best_bid) / mid

            bid_depth_5 = sum(int(b[1]) for b in bids[:5]) if bids else 0
            ask_depth_5 = sum(int(a[1]) for a in asks[:5]) if asks else 0
            depth_imbalance: float | None = None
            if (bid_depth_5 + ask_depth_5) > 0:
                depth_imbalance = float(bid_depth_5 - ask_depth_5) / float(bid_depth_5 + ask_depth_5)

            l2_metric_row = (
                ts_dt,
                symbol,
                best_bid,
                best_ask,
                rel_spread,
                bid_depth_5,
                ask_depth_5,
                depth_imbalance,
            )
            self.l2_metrics_batch.append(l2_metric_row)

        elif topic == Topics.SOCIAL_MESSAGES_RAW:
            raw_event_id = str(data.get("event_id", ""))
            platform = data.get("platform", "telegram")
            event_uuid = to_event_uuid(platform, raw_event_id)

            social_row = (
                parse_dt(data.get("ts_posted")),
                event_uuid,
                platform,
                str(data.get("channel_id", "")),
                data.get("channel_name"),
                data.get("channel_visibility", "public"),
                str(data.get("message_id", "")),
                str(data.get("author_id", "")),
                str(data.get("text", "")),
                data.get("lang"),
                data.get("reply_to_message_id"),
                data.get("forwarded_from_channel_id"),
                data.get("views"),
                data.get("reactions"),
                data.get("urls") or [],
                str(data.get("raw_sha256", "")),
                bool(data.get("is_synthetic", False)),
                parse_dt(data.get("ts_ingest")),
                raw_event_id,
            )
            self.social_batch.append(social_row)

        elif topic == Topics.SOCIAL_SIGNALS_NORM:
            platform = data.get("platform", "telegram")
            signal_id_raw = str(data.get("signal_id", ""))
            msg_event_id_raw = str(data.get("message_event_id", ""))
            signal_uuid = to_event_uuid(platform, signal_id_raw)
            msg_event_uuid = to_event_uuid(platform, msg_event_id_raw)

            parser_meta = data.get("parser") or {}
            signal_row = (
                parse_dt(data.get("ts_posted")),
                signal_uuid,
                msg_event_uuid,
                platform,
                str(data.get("channel_id", "")),
                str(data.get("author_id", "")),
                str(data.get("ticker", "UNKNOWN")),
                float(data.get("ticker_confidence", 1.0)),
                data.get("mention_type"),
                str(data.get("cta_class", "NEUTRAL")),
                float(data.get("cta_confidence", 0.8)) if data.get("cta_confidence") is not None else None,
                Decimal(str(data.get("target_price"))) if data.get("target_price") else None,
                parse_dt(data.get("scheduled_action_time")) if data.get("scheduled_action_time") else None,
                float(data.get("urgency", 0.0)),
                float(data.get("sentiment", 0.0)) if data.get("sentiment") is not None else None,
                data.get("near_dup_cluster_id"),
                int(data.get("forward_cascade_depth", 0)),
                str(data.get("raw_sha256", "")),
                str(parser_meta.get("mode", "FALLBACK_RULES")),
                parser_meta.get("version", "1.0.0"),
            )
            self.signals_batch.append(signal_row)

        elif topic == Topics.HYPE_SCORES_NORM:
            ts_dt = parse_dt(data.get("ts"))
            ticker = str(data.get("ticker") or data.get("symbol", "UNKNOWN"))
            self.watermarks[ticker] = max(self.watermarks.get(ticker, 0.0), ts_dt.timestamp())

            hype_row = (
                ts_dt,
                ticker,
                float(data.get("hype_score", 0.0)),
                float(data.get("f_rate", 0.0)),
                float(data.get("f_auth", 0.0)),
                float(data.get("f_cta", 0.0)),
                float(data.get("f_dup", 0.0)),
                float(data.get("f_urg", 0.0)),
                float(data.get("f_xch", 0.0)),
                int(data.get("msg_count", 0)),
                int(data.get("unique_authors", 0)),
                int(data.get("channels", 0)),
            )
            self.hype_batch.append(hype_row)

        elif topic in (Topics.ANOMALY_MARKET, Topics.ANOMALY_SOCIAL, Topics.ANOMALY_FUSED):
            source_agent = str(data.get("source_agent", "UNKNOWN"))
            anom_id_raw = str(data.get("anomaly_id", ""))
            anom_uuid = to_event_uuid(source_agent, anom_id_raw)
            case_id_val = to_event_uuid("case", str(data.get("case_id"))) if data.get("case_id") else None

            anom_row = (
                parse_dt(data.get("detected_at")),
                anom_uuid,
                str(data.get("type", "UNKNOWN")),
                source_agent,
                str(data.get("symbol", "UNKNOWN")),
                parse_dt(data.get("window_start")),
                parse_dt(data.get("window_end")),
                float(data.get("score", 0.0)),
                str(data.get("severity", "LOW")),
                json.dumps(data.get("metrics") or {}),
                data.get("participants") or [],
                json.dumps(data.get("evidence_refs") or []),
                str(data.get("detector_version", "1.0.0")),
                str(data.get("config_hash", "")),
                case_id_val,
            )
            self.anomalies_batch.append(anom_row)

    async def _flush_all_with_retry(self, records: list[Any]) -> bool:
        max_retries = 3
        backoff = 0.1

        for attempt in range(max_retries):
            try:
                await self._execute_flush()
                return True
            except Exception as exc:
                self.stats["retries"] += 1
                logger.warning("Flush attempt failed, retrying...", attempt=attempt + 1, error=str(exc))
                if attempt < max_retries - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                else:
                    logger.error("All flush retries failed! Routing batch to DLQ and committing offsets.", error=str(exc))
                    for rec in records:
                        await self._send_to_dlq(rec.value, rec.topic, error=str(exc), stage="flush")
                    # Clear failing batches to allow progress
                    self._clear_batches()
                    return False
        return False

    def _clear_batches(self) -> None:
        self.trade_batch = []
        self.l2_batch = []
        self.l2_metrics_batch = []
        self.l3_batch = []
        self.social_batch = []
        self.signals_batch = []
        self.hype_batch = []
        self.anomalies_batch = []

    async def _execute_flush(self) -> None:
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if self.trade_batch:
                    batch = self.trade_batch
                    await conn.executemany(
                        """
                        INSERT INTO vigil.trades (
                            ts, event_id, exchange, symbol, trade_id, seq, price, qty, aggressor_side,
                            buyer_account, seller_account, buyer_broker, seller_broker, buyer_gateway, seller_gateway,
                            buy_order_id, sell_order_id, buyer_device, seller_device, buyer_ip, seller_ip,
                            buyer_asn, seller_asn, buyer_api_client, seller_api_client, buyer_latency_us, seller_latency_us,
                            market_segment, is_synthetic, ts_ingest, source_event_id
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31)
                        ON CONFLICT (symbol, trade_id, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["trades"] += len(batch)
                    self.stats["inserted"] += len(batch)
                    self.trade_batch = []

                if self.l3_batch:
                    batch = self.l3_batch
                    await conn.executemany(
                        """
                        INSERT INTO vigil.orders_l3 (
                            ts, event_id, exchange, symbol, seq, order_id, orig_order_id, action, side, order_type,
                            price, qty, leaves_qty, account_id, broker_id, gateway_id, device_fp, ip_hash,
                            asn, api_client_id, order_to_ack_us, is_synthetic, ts_ingest, source_event_id
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24)
                        ON CONFLICT (symbol, seq, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["l3"] += len(batch)
                    self.stats["inserted"] += len(batch)
                    self.l3_batch = []

                if self.l2_batch:
                    batch = self.l2_batch
                    await conn.executemany(
                        """
                        INSERT INTO vigil.l2_snapshots (
                            ts, symbol, seq, exchange, bids, asks, depth_levels, is_synthetic
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                        ON CONFLICT (symbol, seq, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["l2"] += len(batch)
                    self.stats["inserted"] += len(batch)
                    self.l2_batch = []

                if self.l2_metrics_batch:
                    batch = self.l2_metrics_batch
                    await conn.executemany(
                        """
                        INSERT INTO vigil.l2_metrics_1s (
                            ts, symbol, best_bid, best_ask, rel_spread, bid_depth_5, ask_depth_5, depth_imbalance
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                        ON CONFLICT (symbol, ts) DO UPDATE SET
                            best_bid = EXCLUDED.best_bid,
                            best_ask = EXCLUDED.best_ask,
                            rel_spread = EXCLUDED.rel_spread,
                            bid_depth_5 = EXCLUDED.bid_depth_5,
                            ask_depth_5 = EXCLUDED.ask_depth_5,
                            depth_imbalance = EXCLUDED.depth_imbalance;
                        """,
                        batch,
                    )
                    self.stats["l2_metrics"] += len(batch)
                    self.stats["inserted"] += len(batch)
                    self.l2_metrics_batch = []

                if self.social_batch:
                    batch = self.social_batch
                    await conn.executemany(
                        """
                        INSERT INTO vigil.social_messages (
                            ts, event_id, platform, channel_id, channel_name, channel_visibility, message_id,
                            author_id, text, lang, reply_to_message_id, forwarded_from_channel_id, views, reactions,
                            urls, raw_sha256, is_synthetic, ts_ingest, source_event_id
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
                        ON CONFLICT (platform, channel_id, message_id, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["social"] += len(batch)
                    self.stats["inserted"] += len(batch)
                    self.social_batch = []

                if self.signals_batch:
                    batch = self.signals_batch
                    await conn.executemany(
                        """
                        INSERT INTO vigil.social_signals (
                            ts, signal_id, message_event_id, platform, channel_id, author_id, ticker,
                            ticker_confidence, mention_type, cta_class, cta_confidence, target_price,
                            scheduled_action_time, urgency, sentiment, near_dup_cluster_id,
                            forward_cascade_depth, raw_sha256, parser_mode, parser_version
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
                        ON CONFLICT (signal_id, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["signals"] += len(batch)
                    self.stats["inserted"] += len(batch)
                    self.signals_batch = []

                if self.hype_batch:
                    batch = self.hype_batch
                    await conn.executemany(
                        """
                        INSERT INTO vigil.hype_scores (
                            ts, ticker, hype_score, f_rate, f_auth, f_cta, f_dup, f_urg, f_xch,
                            msg_count, unique_authors, channels
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                        ON CONFLICT (ticker, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["hype"] += len(batch)
                    self.stats["inserted"] += len(batch)
                    self.hype_batch = []

                if self.anomalies_batch:
                    batch = self.anomalies_batch
                    await conn.executemany(
                        """
                        INSERT INTO vigil.anomalies (
                            detected_at, anomaly_id, type, source_agent, symbol, window_start, window_end,
                            score, severity, metrics, participants, evidence_refs, detector_version,
                            config_hash, case_id
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                        ON CONFLICT (anomaly_id, detected_at) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["anomalies"] += len(batch)
                    self.stats["inserted"] += len(batch)
                    self.anomalies_batch = []

        # Flush watermarks to Redis
        if self.redis_client and self.watermarks:
            try:
                async with self.redis_client.pipeline(transaction=True) as pipe:
                    for sym, wm_ts in self.watermarks.items():
                        pipe.set(f"watermark:{sym}", str(wm_ts))
                    pipe.set("watermark:global", str(max(self.watermarks.values())))
                    await pipe.execute()
            except Exception as exc:
                logger.warning("Failed to update watermarks in Redis", error=str(exc))

        logger.info(
            "Stream sink flushed batch successfully",
            inserted=self.stats["inserted"],
            dlq=self.stats["dlq"],
            retries=self.stats["retries"],
        )

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.pool:
            await self.pool.close()
        if self.redis_client:
            await self.redis_client.aclose()
        logger.info("Stream sink stopped cleanly", **self.stats)


async def run() -> None:
    setup_logging()
    sink = StreamSink()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(sink.start())

    await stop_event.wait()
    await sink.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
