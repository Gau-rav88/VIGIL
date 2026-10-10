from __future__ import annotations

import asyncio
import datetime
import json
import os
import signal
import uuid
from decimal import Decimal
from typing import Any

import asyncpg
from aiokafka import AIOKafkaConsumer
from vigil_common.logging import get_logger, setup_logging

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
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.pg_dsn = os.getenv("PG_DSN", "postgresql://vigil:vigil@timescale:5432/vigil")
        self.pool: asyncpg.Pool | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self.running = False

        self.trade_batch: list[tuple[Any, ...]] = []
        self.l2_batch: list[tuple[Any, ...]] = []
        self.l3_batch: list[tuple[Any, ...]] = []
        self.social_batch: list[tuple[Any, ...]] = []
        self.signals_batch: list[tuple[Any, ...]] = []
        self.hype_batch: list[tuple[Any, ...]] = []
        self.anomalies_batch: list[tuple[Any, ...]] = []

        self.stats = {
            "trades": 0,
            "l2": 0,
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

        topics = [
            "market.trades.norm",
            "market.l2.norm",
            "market.l3.norm",
            "social.messages.raw",
            "social.signals.norm",
            "hype.scores.norm",
            "anomaly.market",
            "anomaly.social",
        ]
        logger.info("Connecting to Redpanda consumer...", bootstrap=self.kafka_bootstrap, topics=topics)
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.kafka_bootstrap,
            group_id="stream_sink_workers",
            auto_offset_reset="latest",
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
        )
        await self.consumer.start()
        logger.info("Kafka consumer started")

        flush_task = asyncio.create_task(self._periodic_flush())

        try:
            async for record in self.consumer:
                if not self.running:
                    break
                self._buffer_record(record.topic, record.value)
                if (
                    len(self.trade_batch) >= 200
                    or len(self.l3_batch) >= 200
                    or len(self.l2_batch) >= 200
                    or len(self.social_batch) >= 50
                    or len(self.signals_batch) >= 50
                    or len(self.hype_batch) >= 50
                    or len(self.anomalies_batch) >= 10
                ):
                    await self._flush_all()
        finally:
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass

    def _buffer_record(self, topic: str, value_bytes: bytes) -> None:
        try:
            data = json.loads(value_bytes)
            if topic == "market.trades.norm":
                buyer = data.get("buyer") or {}
                seller = data.get("seller") or {}
                trade_row = (
                    parse_dt(data.get("ts_exchange")),
                    uuid.UUID(data.get("event_id")),
                    data.get("exchange", "SYNTH"),
                    data.get("symbol", "UNKNOWN"),
                    data.get("trade_id", "T-0"),
                    int(data.get("seq", 0)),
                    Decimal(str(data.get("price", "0.0"))),
                    int(data.get("qty", 0)),
                    data.get("aggressor_side", "UNKNOWN"),
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
                )
                self.trade_batch.append(trade_row)

            elif topic == "market.l3.norm":
                l3_row = (
                    parse_dt(data.get("ts_exchange")),
                    uuid.UUID(data.get("event_id")),
                    data.get("exchange", "SYNTH"),
                    data.get("symbol", "UNKNOWN"),
                    int(data.get("seq", 0)),
                    data.get("order_id", ""),
                    data.get("orig_order_id"),
                    data.get("action", "NEW"),
                    data.get("side", "BUY"),
                    data.get("order_type"),
                    Decimal(str(data.get("price", "0.0"))) if data.get("price") else None,
                    int(data.get("qty")) if data.get("qty") is not None else None,
                    int(data.get("leaves_qty")) if data.get("leaves_qty") is not None else None,
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
                )
                self.l3_batch.append(l3_row)

            elif topic == "market.l2.norm":
                l2_row = (
                    parse_dt(data.get("ts_exchange")),
                    data.get("symbol", "UNKNOWN"),
                    int(data.get("seq", 0)),
                    data.get("exchange", "SYNTH"),
                    json.dumps(data.get("bids", [])),
                    json.dumps(data.get("asks", [])),
                    int(data.get("depth_levels", 10)),
                    bool(data.get("is_synthetic", False)),
                )
                self.l2_batch.append(l2_row)

            elif topic == "social.messages.raw":
                social_row = (
                    parse_dt(data.get("ts_posted")),
                    uuid.UUID(data.get("event_id")),
                    data.get("platform", "telegram"),
                    data.get("channel_id", ""),
                    data.get("channel_name"),
                    data.get("channel_visibility", "public"),
                    data.get("message_id", ""),
                    data.get("author_id", ""),
                    data.get("text", ""),
                    data.get("lang"),
                    data.get("reply_to_message_id"),
                    data.get("forwarded_from_channel_id"),
                    data.get("views"),
                    data.get("reactions"),
                    data.get("urls") or [],
                    data.get("raw_sha256", ""),
                    bool(data.get("is_synthetic", False)),
                    parse_dt(data.get("ts_ingest")),
                )
                self.social_batch.append(social_row)

            elif topic == "social.signals.norm":
                parser_meta = data.get("parser") or {}
                signal_row = (
                    parse_dt(data.get("ts_posted")),
                    uuid.UUID(data.get("signal_id")),
                    uuid.UUID(data.get("message_event_id")),
                    data.get("platform", "telegram"),
                    data.get("channel_id", ""),
                    data.get("author_id", ""),
                    data.get("ticker", "UNKNOWN"),
                    float(data.get("ticker_confidence", 1.0)),
                    data.get("mention_type"),
                    data.get("cta_class", "NEUTRAL"),
                    float(data.get("cta_confidence", 0.8)) if data.get("cta_confidence") is not None else None,
                    Decimal(str(data.get("target_price"))) if data.get("target_price") else None,
                    parse_dt(data.get("scheduled_action_time")) if data.get("scheduled_action_time") else None,
                    float(data.get("urgency", 0.0)),
                    float(data.get("sentiment", 0.0)) if data.get("sentiment") is not None else None,
                    data.get("near_dup_cluster_id"),
                    int(data.get("forward_cascade_depth", 0)),
                    data.get("raw_sha256", ""),
                    parser_meta.get("mode", "FALLBACK_RULES"),
                    parser_meta.get("version", "1.0.0"),
                )
                self.signals_batch.append(signal_row)

            elif topic == "hype.scores.norm":
                hype_row = (
                    parse_dt(data.get("ts")),
                    data.get("ticker", "UNKNOWN"),
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

            elif topic in ("anomaly.market", "anomaly.social"):
                case_id_val = uuid.UUID(data.get("case_id")) if data.get("case_id") else None
                anom_row = (
                    parse_dt(data.get("detected_at")),
                    uuid.UUID(data.get("anomaly_id")),
                    data.get("type", "UNKNOWN"),
                    data.get("source_agent", "UNKNOWN"),
                    data.get("symbol", "UNKNOWN"),
                    parse_dt(data.get("window_start")),
                    parse_dt(data.get("window_end")),
                    float(data.get("score", 0.0)),
                    data.get("severity", "LOW"),
                    json.dumps(data.get("metrics") or {}),
                    data.get("participants") or [],
                    json.dumps(data.get("evidence_refs") or []),
                    data.get("detector_version", "1.0.0"),
                    data.get("config_hash", ""),
                    case_id_val,
                )
                self.anomalies_batch.append(anom_row)

        except Exception as exc:
            logger.error("Error buffering record", topic=topic, error=str(exc))

    async def _flush_all(self) -> None:
        if not self.pool:
            return

        async with self.pool.acquire() as conn:
            if self.trade_batch:
                batch = self.trade_batch
                self.trade_batch = []
                try:
                    await conn.executemany(
                        """
                        INSERT INTO vigil.trades (
                            ts, event_id, exchange, symbol, trade_id, seq, price, qty, aggressor_side,
                            buyer_account, seller_account, buyer_broker, seller_broker, buyer_gateway, seller_gateway,
                            buy_order_id, sell_order_id, buyer_device, seller_device, buyer_ip, seller_ip,
                            buyer_asn, seller_asn, buyer_api_client, seller_api_client, buyer_latency_us, seller_latency_us,
                            market_segment, is_synthetic, ts_ingest
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30)
                        ON CONFLICT (symbol, trade_id, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["trades"] += len(batch)
                except Exception as exc:
                    logger.error("Failed to insert trades", error=str(exc))

            if self.l3_batch:
                batch = self.l3_batch
                self.l3_batch = []
                try:
                    await conn.executemany(
                        """
                        INSERT INTO vigil.orders_l3 (
                            ts, event_id, exchange, symbol, seq, order_id, orig_order_id, action, side, order_type,
                            price, qty, leaves_qty, account_id, broker_id, gateway_id, device_fp, ip_hash,
                            asn, api_client_id, order_to_ack_us, is_synthetic, ts_ingest
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
                        ON CONFLICT (symbol, seq, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["l3"] += len(batch)
                except Exception as exc:
                    logger.error("Failed to insert L3 orders", error=str(exc))

            if self.l2_batch:
                batch = self.l2_batch
                self.l2_batch = []
                try:
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
                except Exception as exc:
                    logger.error("Failed to insert L2 snapshots", error=str(exc))

            if self.social_batch:
                batch = self.social_batch
                self.social_batch = []
                try:
                    await conn.executemany(
                        """
                        INSERT INTO vigil.social_messages (
                            ts, event_id, platform, channel_id, channel_name, channel_visibility, message_id,
                            author_id, text, lang, reply_to_message_id, forwarded_from_channel_id, views, reactions,
                            urls, raw_sha256, is_synthetic, ts_ingest
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
                        ON CONFLICT (platform, channel_id, message_id, ts) DO NOTHING;
                        """,
                        batch,
                    )
                    self.stats["social"] += len(batch)
                except Exception as exc:
                    logger.error("Failed to insert social messages", error=str(exc))

            if self.signals_batch:
                batch = self.signals_batch
                self.signals_batch = []
                try:
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
                except Exception as exc:
                    logger.error("Failed to insert social signals", error=str(exc))

            if self.hype_batch:
                batch = self.hype_batch
                self.hype_batch = []
                try:
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
                except Exception as exc:
                    logger.error("Failed to insert hype scores", error=str(exc))

            if self.anomalies_batch:
                batch = self.anomalies_batch
                self.anomalies_batch = []
                try:
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
                except Exception as exc:
                    logger.error("Failed to insert anomalies", error=str(exc))

    async def _periodic_flush(self) -> None:
        while self.running:
            await asyncio.sleep(0.5)
            await self._flush_all()

    async def stop(self) -> None:
        self.running = False
        await self._flush_all()
        if self.consumer:
            await self.consumer.stop()
        if self.pool:
            await self.pool.close()
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
