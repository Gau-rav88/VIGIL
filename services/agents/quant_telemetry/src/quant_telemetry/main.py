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
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from vigil_common.logging import get_logger, setup_logging
from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

logger = get_logger("quant_telemetry")


class QuantTelemetryDetector:
    def __init__(self) -> None:
        self.kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
        self.consumer: AIOKafkaConsumer | None = None
        self.producer: AIOKafkaProducer | None = None
        self.running = False

        # Per symbol rolling stats: symbol -> deque of (timestamp, volume, price)
        self.trade_windows: dict[str, collections.deque[tuple[float, int, float, str, str, str]]] = (
            collections.defaultdict(lambda: collections.deque(maxlen=10000))
        )
        # Account order history for spoofing: (symbol, account_id) -> deque of (order_id, action, qty, price, ts)
        self.order_history: dict[tuple[str, str], collections.deque[dict[str, Any]]] = (
            collections.defaultdict(lambda: collections.deque(maxlen=1000))
        )
        # Cooldown per symbol & anomaly type to avoid flooding
        self.cooldowns: dict[tuple[str, str], float] = {}

        self.config_hash = hashlib.sha256(b"quant_telemetry_detectors_v1").hexdigest()

    async def start(self) -> None:
        self.running = True
        logger.info("Starting quant_telemetry detector...", bootstrap=self.kafka_bootstrap)

        self.producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap, acks=1)
        await self.producer.start()

        self.consumer = AIOKafkaConsumer(
            "market.trades.norm",
            "market.l3.norm",
            bootstrap_servers=self.kafka_bootstrap,
            group_id="quant_telemetry_workers",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()
        logger.info("Connected to market.trades.norm and market.l3.norm")

        async for record in self.consumer:
            if not self.running:
                break
            try:
                data = json.loads(record.value)
                if record.topic == "market.trades.norm":
                    await self._process_trade(data)
                elif record.topic == "market.l3.norm":
                    await self._process_l3(data)
            except Exception as exc:
                logger.error("Error processing quant telemetry record", error=str(exc))

    async def _process_trade(self, trade: dict[str, Any]) -> None:
        sym = trade.get("symbol", "UNKNOWN")
        price = float(trade.get("price", 0.0))
        qty = int(trade.get("qty", 0))
        trade_id = trade.get("trade_id", "")
        buyer_acc = trade.get("buyer", {}).get("account_id", "")
        seller_acc = trade.get("seller", {}).get("account_id", "")
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

        win = self.trade_windows[sym]
        win.append((now_ts, qty, price, trade_id, buyer_acc, seller_acc))

        # Check volume spike & price jump if enough samples
        if len(win) >= 20:
            recent_qty = [w[1] for w in win]
            mean_qty = sum(recent_qty) / len(recent_qty)
            std_qty = (sum((q - mean_qty) ** 2 for q in recent_qty) / len(recent_qty)) ** 0.5

            # Volume Spike Check
            z_score = (qty - mean_qty) / max(1.0, std_qty)
            z_thr = 3.5 if "SME" in sym else 4.5
            if z_score >= z_thr:
                await self._emit_anomaly(
                    sym=sym,
                    anom_type="VOLUME_SPIKE",
                    score=min(1.0, 0.5 + z_score * 0.1),
                    severity="HIGH" if z_score >= 5.0 else "MEDIUM",
                    metrics={"z_score": round(z_score, 2), "trade_qty": qty, "mean_qty": round(mean_qty, 2)},
                    evidence=[EvidenceRef(kind="trade_id", ref=trade_id)],
                    participants=[buyer_acc, seller_acc],
                )

            # Price Jump Check (compare current price vs price 30s ago)
            cutoff = now_ts - 30.0
            past_prices = [w[2] for w in win if w[0] <= cutoff]
            if past_prices:
                baseline_p = past_prices[-1]
                pct_change = abs((price - baseline_p) / baseline_p) * 100.0
                if pct_change >= 5.0:
                    await self._emit_anomaly(
                        sym=sym,
                        anom_type="PRICE_JUMP",
                        score=min(1.0, pct_change / 20.0),
                        severity="HIGH" if pct_change >= 10.0 else "MEDIUM",
                        metrics={"pct_change": round(pct_change, 2), "current_price": price, "baseline_price": baseline_p},
                        evidence=[EvidenceRef(kind="trade_id", ref=trade_id)],
                        participants=[buyer_acc, seller_acc],
                    )

        # Wash Cycle Check: circular trading between same accounts
        if len(win) >= 6:
            recent_trades = list(win)[-6:]
            # Look for 2-cycle: A -> B and B -> A with similar qty
            for i in range(len(recent_trades) - 1):
                t1 = recent_trades[i]
                t2 = recent_trades[-1]
                if t1[4] == t2[5] and t1[5] == t2[4] and abs(t1[1] - t2[1]) <= max(1, 0.05 * t1[1]):
                    # Matched circular trade detected!
                    await self._emit_anomaly(
                        sym=sym,
                        anom_type="WASH_CYCLE",
                        score=0.92,
                        severity="HIGH",
                        metrics={"cycle_len": 2, "qty": t2[1], "price": t2[2]},
                        evidence=[EvidenceRef(kind="trade_id", ref=t1[3]), EvidenceRef(kind="trade_id", ref=t2[3])],
                        participants=[t1[4], t1[5]],
                    )
                    break

    async def _process_l3(self, order: dict[str, Any]) -> None:
        sym = order.get("symbol", "UNKNOWN")
        acc_id = order.get("account_id", "")
        action = order.get("action", "")
        oid = order.get("order_id", "")
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

        history = self.order_history[(sym, acc_id)]
        history.append({
            "order_id": oid,
            "action": action,
            "ts": now_ts,
        })

        # Check spoofing/layering within last 10 seconds
        cutoff = now_ts - 10.0
        recent = [o for o in history if o["ts"] >= cutoff]
        if len(recent) >= 6:
            cancels = sum(1 for o in recent if o["action"] == "CANCEL")
            news = sum(1 for o in recent if o["action"] == "NEW")
            if news >= 4 and cancels / max(1, (cancels + news)) >= 0.7:
                await self._emit_anomaly(
                    sym=sym,
                    anom_type="SPOOFING_LAYERING",
                    score=0.88,
                    severity="HIGH",
                    metrics={"orders": len(recent), "cancels": cancels, "cancel_ratio": round(cancels / len(recent), 2)},
                    evidence=[EvidenceRef(kind="order_id", ref=o["order_id"]) for o in recent[:5]],
                    participants=[acc_id],
                )

    async def _emit_anomaly(
        self,
        sym: str,
        anom_type: str,
        score: float,
        severity: str,
        metrics: dict[str, Any],
        evidence: list[EvidenceRef],
        participants: list[str],
    ) -> None:
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        key = (sym, anom_type)
        if key in self.cooldowns and (now_ts - self.cooldowns[key]) < 10.0:
            return  # In cooldown
        self.cooldowns[key] = now_ts

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        start_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)).isoformat()

        event = AnomalyEvent(
            schema_version="1.0.0",
            anomaly_id=str(uuid.uuid4()),
            type=anom_type,  # type: ignore[arg-type]
            source_agent="quant_telemetry",
            symbol=sym,
            window_start=start_iso,
            window_end=now_iso,
            score=min(1.0, max(0.0, score)),
            severity=severity,  # type: ignore[arg-type]
            metrics=metrics,
            participants=[p for p in participants if p],
            evidence_refs=evidence,
            detector_version="1.0.0",
            config_hash=self.config_hash,
            detected_at=now_iso,
        )

        logger.info("Detected market anomaly", type=anom_type, symbol=sym, score=score)
        if self.producer:
            await self.producer.send(
                topic="anomaly.market",
                value=json.dumps(event.model_dump()).encode("utf-8"),
                key=sym.encode("utf-8"),
            )

    async def stop(self) -> None:
        self.running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Quant telemetry detector stopped cleanly")


async def run() -> None:
    setup_logging()
    detector = QuantTelemetryDetector()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _sig_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _sig_handler)

    task = asyncio.create_task(detector.start())

    await stop_event.wait()
    await detector.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
