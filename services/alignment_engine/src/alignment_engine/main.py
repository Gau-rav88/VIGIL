"""Full Phase 4 alignment engine — cross-modal alignment + MRS.

Tasks implemented:
- P4-T01: Series assembly (1-s grid h/v/a/spread_rel from TimescaleDB)
- P4-T02: FFT normalized xcorr for lags -120..+1800s
- P4-T03: Circular block-shuffle permutation test (B=500, seeded)
- P4-T04: Event fast path — HYPE_BURST + VOLUME_SPIKE|PRICE_JUMP within 15 min
- P4-T05: 30-s watermark; series recomputed from Timescale each cycle
- P4-T06: MRS per ticker per minute, persisted to mrs_1m + Redis mrs:{symbol}
- P4-T07: Publish CROSS_MODAL_ALIGNMENT to anomaly.fused + CaseTrigger to case.trigger
"""
from __future__ import annotations

import asyncio
import collections
import datetime
import hashlib
import json
import os
import signal
import uuid
from typing import Any

import asyncpg
import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from numpy import median, zeros
from vigil_common.logging import get_logger, setup_logging
from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef
from vigil_common.network import resolve_db_dsn, resolve_kafka_bootstrap, resolve_redis_url

from alignment_engine.mrs import MICRO_ANOMALY_TYPES, compute_mrs
from alignment_engine.series import ALIGN_LOOKBACK_S, fetch_series
from alignment_engine.xcorr import normalized_xcorr, permutation_test

logger = get_logger("alignment_engine")

# --- Configuration ---
ALIGN_CYCLE_S = 60        # run alignment per ticker every 60 seconds
FAST_PATH_WINDOW_S = 900  # HYPE_BURST + market anomaly within 15 min
COOLDOWN_S = 30           # suppress duplicate CROSS_MODAL_ALIGNMENT per ticker
P_THRESHOLD = 0.01        # permutation test significance threshold
LAG_MIN_S = -120
LAG_MAX_S = 1800
MRS_REDIS_TTL = 120       # TTL for mrs:{symbol} in Redis


class AlignmentEngine:
    def __init__(self) -> None:
        self.kafka_bootstrap = resolve_kafka_bootstrap(os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092"))
        self.db_dsn = resolve_db_dsn(
            os.getenv(
                "TIMESCALE_DSN",
                "postgresql://vigil:vigil@timescale:5432/vigil",
            )
        )
        self.redis_url = resolve_redis_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.db_pool: Any = None
        self.redis: Any = None
        self.running = False

        # Anomaly history: symbol → {social: [...], market: [...]}
        self.history: dict[str, dict[str, list[dict[str, Any]]]] = collections.defaultdict(
            lambda: {"social": [], "market": []}
        )
        # Cooldown per ticker for emitting CROSS_MODAL_ALIGNMENT
        self.cooldowns: dict[str, float] = {}

        # MRS state: symbol → latest values
        self.hype_cache: dict[str, float] = {}    # latest hype score
        self.volume_z_cache: dict[str, float] = {}
        self.xcorr_cache: dict[str, tuple[float, float]] = {}  # (xcorr_peak, p_value)
        self.micro_cache: dict[str, float] = {}   # micro-structure score

        self.config_hash = hashlib.sha256(b"alignment_engine_v2").hexdigest()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self.running = True
        logger.info("Starting alignment_engine v2", bootstrap=self.kafka_bootstrap)

        # Kafka producer
        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        # Kafka consumer — anomaly streams + hype scores
        self.consumer = AIOKafkaConsumer(
            "anomaly.market",
            "anomaly.social",
            "hype.scores.norm",
            bootstrap_servers=self.kafka_bootstrap,
            group_id="alignment_engine_workers_v3",
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Connected to Kafka topics")

        # TimescaleDB connection pool
        try:
            self.db_pool = await asyncpg.create_pool(
                self.db_dsn,
                min_size=2,
                max_size=8,
                command_timeout=30.0,
            )
            logger.info("Connected to TimescaleDB")
        except Exception as exc:
            logger.warning("TimescaleDB unavailable — alignment will run event-fast-path only", error=str(exc))
            self.db_pool = None

        # Redis
        try:
            self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
            ping_obj: Any = self.redis.ping()
            if hasattr(ping_obj, "__await__"):
                await ping_obj
            logger.info("Connected to Redis")
        except Exception as exc:
            logger.warning("Redis unavailable — MRS will not be cached", error=str(exc))
            self.redis = None

        # Start the periodic MRS cycle (every 60s)
        mrs_task = asyncio.create_task(self._mrs_loop())

        try:
            async for record in self.consumer:
                if not self.running:
                    break
                try:
                    data = json.loads(record.value)
                    await self._process_record(record.topic, data)
                except Exception as exc:
                    logger.error("Error processing record", topic=record.topic, error=str(exc))
        finally:
            mrs_task.cancel()
            try:
                await mrs_task
            except asyncio.CancelledError:
                pass

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.db_pool:
            await self.db_pool.close()
        if self.redis:
            await self.redis.aclose()
        logger.info("Alignment engine stopped cleanly")

    # ------------------------------------------------------------------
    # Record dispatch
    # ------------------------------------------------------------------

    async def _process_record(self, topic: str, data: dict[str, Any]) -> None:
        if topic == "hype.scores.norm":
            await self._on_hype_score(data)
        elif topic in ("anomaly.social", "anomaly.market"):
            await self._on_anomaly(topic, data)

    async def _on_hype_score(self, data: dict[str, Any]) -> None:
        sym = data.get("symbol") or data.get("ticker", "UNKNOWN")
        score = float(data.get("hype_score", 0.0))
        self.hype_cache[sym] = score

    async def _on_anomaly(self, topic: str, anom: dict[str, Any]) -> None:
        sym = anom.get("symbol", "UNKNOWN")
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        ts = now_ts
        logger.info("Alignment engine received anomaly", topic=topic, symbol=sym, anomaly_type=anom.get("type"))

        # Update micro-structure cache for MRS component
        anom_type = anom.get("type", "")
        if anom_type in MICRO_ANOMALY_TYPES:
            current = self.micro_cache.get(sym, 0.0)
            self.micro_cache[sym] = max(current, float(anom.get("score", 0.0)))

        # Clean history > 30 min
        bucket = self.history[sym]
        cutoff = now_ts - 1800.0
        bucket["social"] = [a for a in bucket["social"] if a["_ts"] >= cutoff]
        bucket["market"] = [a for a in bucket["market"] if a["_ts"] >= cutoff]

        anom["_ts"] = ts

        if topic == "anomaly.social":
            bucket["social"].append(anom)
        else:
            bucket["market"].append(anom)

        # Check event fast path
        await self._check_fast_path(sym, now_ts)

    # ------------------------------------------------------------------
    # Event fast path (P4-T04)
    # ------------------------------------------------------------------

    async def _check_fast_path(self, sym: str, now_ts: float) -> None:
        """HYPE_BURST + VOLUME_SPIKE|PRICE_JUMP within 15 min → fast-path alignment."""
        bucket = self.history[sym]

        hype_bursts = [
            a for a in bucket["social"]
            if a.get("type") == "HYPE_BURST"
        ]
        market_events = [
            a for a in bucket["market"]
            if a.get("type") in ("VOLUME_SPIKE", "PRICE_JUMP", "WASH_CYCLE", "SPREAD_WIDENING", "DEPTH_IMBALANCE")
        ]

        logger.info(
            "Fast path check",
            symbol=sym,
            hype_bursts=len(hype_bursts),
            market_events=len(market_events),
        )

        if not hype_bursts or not market_events:
            return

        cooldown = self.cooldowns.get(sym, 0.0)
        if 0.0 <= (now_ts - cooldown) < COOLDOWN_S:
            return

        for burst in reversed(hype_bursts):
            for mev in reversed(market_events):
                lag_s = mev["_ts"] - burst["_ts"]
                if -60.0 <= lag_s <= FAST_PATH_WINDOW_S:
                    self.cooldowns[sym] = now_ts
                    effective_lag = max(1.0, lag_s)
                    logger.info(
                        "FAST PATH: HYPE_BURST → market anomaly detected",
                        symbol=sym,
                        lag_s=effective_lag,
                        burst_type=burst.get("type"),
                        market_type=mev.get("type"),
                    )
                    await self._emit_alignment(
                        sym=sym,
                        social_anom=burst,
                        market_anom=mev,
                        lag_s=effective_lag,
                        xcorr_peak=0.85,  # estimated for fast-path
                        p_value=0.0,      # qualifies without test
                        fast_path=True,
                    )
                    return

    # ------------------------------------------------------------------
    # MRS loop (P4-T06)
    # ------------------------------------------------------------------

    async def _mrs_loop(self) -> None:
        """Emit MRS for all known symbols every 60 seconds."""
        while self.running:
            await asyncio.sleep(ALIGN_CYCLE_S)
            if not self.running:
                break
            now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
            all_symbols = set(self.hype_cache.keys()) | set(self.history.keys())
            for sym in all_symbols:
                try:
                    await self._run_alignment_and_mrs(sym, now_ts)
                except Exception as exc:
                    logger.error("MRS cycle error", symbol=sym, error=str(exc))

    async def _run_alignment_and_mrs(self, sym: str, now_ts: float) -> None:
        """Full alignment + MRS for one symbol."""
        # --- Fetch time series from TimescaleDB ---
        if self.db_pool is not None:
            async with self.db_pool.acquire() as conn:
                h, v, a, _spread_rel = await fetch_series(conn, sym, now_ts, ALIGN_LOOKBACK_S)
        else:
            # Fallback: minimal arrays
            n = ALIGN_LOOKBACK_S
            h = zeros(n, dtype=float)
            v = zeros(n, dtype=float)
            a = zeros(n, dtype=float)
            _spread_rel = zeros(n, dtype=float)

        # Inject latest hype into h[-1] if available
        if sym in self.hype_cache:
            h[-1] = self.hype_cache[sym]

        # --- Cross-correlation (P4-T02) ---
        best_lag_s, xcorr_peak = normalized_xcorr(h, v, LAG_MIN_S, LAG_MAX_S)

        # --- Permutation test (P4-T03) ---
        window_id = datetime.datetime.fromtimestamp(now_ts, tz=datetime.timezone.utc).strftime("%Y%m%d%H%M")
        p_value = permutation_test(
            h, v, xcorr_peak, sym, window_id, b=500
        )

        # Cache for MRS
        self.xcorr_cache[sym] = (xcorr_peak, p_value)

        # --- Volume z-score ---
        n_vol = max(len(v), 1)
        vol_last = float(v[-1]) if n_vol > 0 else 0.0
        vol_median = float(median(v))
        vol_mad = float(median(abs(v - vol_median)))
        vol_sigma = max(vol_mad * 1.4826, 1e-9)
        volume_z = max(0.0, (vol_last - vol_median) / vol_sigma)
        self.volume_z_cache[sym] = volume_z

        # --- Price component ---
        # |ret_5m| from last 300 samples of a(t) and 1-h sigma from a(t)
        ret_5m = float(a[-300:].sum()) if len(a) >= 300 else float(a.sum())
        sigma_1h = max(float(a[-3600:].std()) if len(a) >= 3600 else float(a.std()), 1e-9)

        # --- Ring score from active cases (placeholder; Phase 5 will fill) ---
        ring_score = 0.0  # updated by orchestrator in Phase 5

        # --- Micro score (cleaned every cycle — only last 5-min relevant) ---
        micro_score = self.micro_cache.pop(sym, 0.0)

        # --- Compute MRS ---
        hype_score = self.hype_cache.get(sym, 0.0)
        mrs, components = compute_mrs(
            hype_score=hype_score,
            volume_z=volume_z,
            xcorr_peak=xcorr_peak,
            p_value=p_value,
            ring_score=ring_score,
            ret_5m=ret_5m,
            sigma_1h=sigma_1h,
            micro_score=micro_score,
        )

        now_iso = datetime.datetime.fromtimestamp(now_ts, tz=datetime.timezone.utc).isoformat()

        logger.info(
            "MRS computed",
            symbol=sym,
            mrs=round(mrs, 2),
            best_lag_s=best_lag_s,
            xcorr_peak=round(xcorr_peak, 4),
            p_value=round(p_value, 4),
        )

        # Persist to TimescaleDB mrs_1m
        if self.db_pool is not None:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO vigil.mrs_1m (ts, symbol, mrs, components)
                        VALUES (to_timestamp($1), $2, $3, $4)
                        ON CONFLICT (symbol, ts) DO UPDATE
                        SET mrs = EXCLUDED.mrs, components = EXCLUDED.components
                        """,
                        now_ts,
                        sym,
                        float(mrs),
                        json.dumps(components),
                    )
            except Exception as exc:
                logger.warning("Failed to persist MRS to TimescaleDB", symbol=sym, error=str(exc))

        # Cache latest in Redis mrs:{symbol}
        if self.redis is not None:
            try:
                payload = json.dumps({
                    "symbol": sym,
                    "ts": now_iso,
                    "mrs": round(mrs, 2),
                    "components": components,
                    "best_lag_s": best_lag_s,
                    "xcorr_peak": round(xcorr_peak, 4),
                    "p_value": round(p_value, 4),
                })
                await self.redis.set(f"mrs:{sym}", payload, ex=MRS_REDIS_TTL)
                # Also update watchlist:symbols
                await self.redis.sadd("watchlist:symbols", sym)
            except Exception as exc:
                logger.warning("Failed to update Redis MRS", symbol=sym, error=str(exc))

        # Trigger statistical alignment if significant
        if (
            p_value < P_THRESHOLD
            and best_lag_s > 0  # social leads
            and xcorr_peak > 0.3
        ):
            cooldown = self.cooldowns.get(sym, 0.0)
            if (now_ts - cooldown) >= COOLDOWN_S:
                self.cooldowns[sym] = now_ts
                # Find most recent social and market anomalies to attach as evidence
                social_anom: dict[str, Any] = {}
                market_anom: dict[str, Any] = {}
                bucket = self.history[sym]
                if bucket["social"]:
                    social_anom = max(bucket["social"], key=lambda x: x["_ts"])
                if bucket["market"]:
                    market_anom = max(bucket["market"], key=lambda x: x["_ts"])

                await self._emit_alignment(
                    sym=sym,
                    social_anom=social_anom,
                    market_anom=market_anom,
                    lag_s=best_lag_s,
                    xcorr_peak=xcorr_peak,
                    p_value=p_value,
                    fast_path=False,
                )

    # ------------------------------------------------------------------
    # Emit fused anomaly + case trigger (P4-T07)
    # ------------------------------------------------------------------

    async def _emit_alignment(
        self,
        sym: str,
        social_anom: dict[str, Any],
        market_anom: dict[str, Any],
        lag_s: float,
        xcorr_peak: float,
        p_value: float,
        fast_path: bool = False,
    ) -> None:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        start_iso = social_anom.get("window_start", now_iso)
        end_iso = market_anom.get("window_end", now_iso)

        evidence: list[EvidenceRef] = []
        if social_anom.get("anomaly_id"):
            evidence.append(EvidenceRef(kind="anomaly_id", ref=social_anom["anomaly_id"]))
        if market_anom.get("anomaly_id"):
            evidence.append(EvidenceRef(kind="anomaly_id", ref=market_anom["anomaly_id"]))
        for ev in social_anom.get("evidence_refs", []):
            evidence.append(EvidenceRef(**ev))
        for ev in market_anom.get("evidence_refs", []):
            evidence.append(EvidenceRef(**ev))

        participants = list(
            set(social_anom.get("participants", []) + market_anom.get("participants", []))
        )

        # Score: high if xcorr is strong and p is very small
        align_strength = xcorr_peak * (1.0 - p_value) if not fast_path else 0.9
        social_s = float(social_anom.get("score", 0.8))
        market_s = float(market_anom.get("score", 0.8))
        score = min(1.0, 0.4 * align_strength + 0.3 * social_s + 0.3 * market_s)

        fused = AnomalyEvent(
            schema_version="1.0.0",
            anomaly_id=str(uuid.uuid4()),
            type="CROSS_MODAL_ALIGNMENT",
            source_agent="orchestrator",
            symbol=sym,
            window_start=start_iso,
            window_end=end_iso,
            score=round(score, 3),
            severity="HIGH" if score >= 0.8 else "MEDIUM",
            metrics={
                "best_lag_s": round(lag_s, 2),
                "xcorr_peak": round(xcorr_peak, 4),
                "p_value": round(p_value, 6),
                "fast_path": fast_path,
                "social_anomaly_type": social_anom.get("type"),
                "market_anomaly_type": market_anom.get("type"),
            },
            participants=participants,
            evidence_refs=evidence[:15],
            detector_version="2.0.0",
            config_hash=self.config_hash,
            detected_at=now_iso,
        )

        logger.info(
            "Emitting CROSS_MODAL_ALIGNMENT",
            symbol=sym,
            best_lag_s=lag_s,
            xcorr_peak=xcorr_peak,
            p_value=p_value,
            fast_path=fast_path,
            score=score,
        )

        payload = json.dumps(fused.model_dump()).encode("utf-8")
        key = sym.encode("utf-8")

        if self.producer:
            await self.producer.send(topic="anomaly.fused", value=payload, key=key)
            await self.producer.send(topic="case.trigger", value=payload, key=key)
            await self.producer.flush()


async def run() -> None:
    setup_logging()
    engine = AlignmentEngine()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(engine.start())

    await stop_event.wait()
    await engine.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
