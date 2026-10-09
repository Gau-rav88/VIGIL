from __future__ import annotations

import datetime
import os
import uuid
from decimal import Decimal

import asyncpg
import pytest


def get_pg_dsn() -> str:
    # Use environment if set, else check standard host port 5434, fallback to 5432
    return os.getenv("TEST_PG_DSN") or os.getenv("PG_DSN_HOST") or "postgresql://vigil:vigil@localhost:5434/vigil"


@pytest.mark.asyncio
async def test_idempotent_replay_trades_invariant() -> None:
    dsn = get_pg_dsn()
    try:
        conn = await asyncpg.connect(dsn)
    except Exception:
        # Fallback to port 5432 if 5434 unreachable
        dsn = "postgresql://vigil:vigil@localhost:5432/vigil"
        conn = await asyncpg.connect(dsn)

    try:
        # Construct a synthetic batch of 10 trades with deterministic keys
        now_dt = datetime.datetime(2026, 3, 14, 5, 0, 0, tzinfo=datetime.timezone.utc)
        symbol = "ZENITHSME"
        batch_trades: list[tuple] = []

        insert_sql = """
        INSERT INTO vigil.trades (
            ts, event_id, exchange, symbol, trade_id, seq, price, qty, aggressor_side,
            buyer_account, seller_account, buyer_broker, seller_broker, buyer_gateway, seller_gateway,
            buy_order_id, sell_order_id, buyer_device, seller_device, buyer_ip, seller_ip,
            buyer_asn, seller_asn, buyer_api_client, seller_api_client, buyer_latency_us, seller_latency_us,
            market_segment, is_synthetic, ts_ingest
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30)
        ON CONFLICT (symbol, trade_id, ts) DO NOTHING;
        """

        for i in range(10):
            ev_id = uuid.uuid5(uuid.NAMESPACE_OID, f"idempotent_replay:{i}")
            tid = f"T-REPLAY-{i:04d}"
            row = (
                now_dt,
                ev_id,
                "SYNTH",
                symbol,
                tid,
                1000 + i,
                Decimal("42.50"),
                500,
                "BUY",
                "ACC_BUYER_000000000000001",
                "ACC_SELLER_000000000000001",
                "BRK-01",
                "BRK-02",
                "GW-1",
                "GW-2",
                f"O-B-{i}",
                f"O-S-{i}",
                "DEV-1",
                "DEV-2",
                "IP-1",
                "IP-2",
                12345,
                54321,
                None,
                None,
                500,
                500,
                "SME",
                True,
                now_dt,
            )
            batch_trades.append(row)

        # Pass 1: First replay insert
        await conn.executemany(insert_sql, batch_trades)
        count_after_first_replay = await conn.fetchval(
            "SELECT count(*) FROM vigil.trades WHERE symbol = $1 AND trade_id LIKE 'T-REPLAY-%';",
            symbol,
        )
        assert count_after_first_replay == 10, f"Expected 10 trades after first replay, got {count_after_first_replay}"

        total_count_1 = await conn.fetchval("SELECT count(*) FROM vigil.trades;")

        # Pass 2: Exact same replay executed a second time (idempotency verification)
        await conn.executemany(insert_sql, batch_trades)

        count_after_second_replay = await conn.fetchval(
            "SELECT count(*) FROM vigil.trades WHERE symbol = $1 AND trade_id LIKE 'T-REPLAY-%';",
            symbol,
        )
        total_count_2 = await conn.fetchval("SELECT count(*) FROM vigil.trades;")

        # Acceptance Criterion AC-ING-04:
        # Replaying the same file twice leaves trades row count unchanged
        assert count_after_second_replay == 10, "Row count for replayed batch changed on second pass!"
        assert total_count_2 == total_count_1, (
            f"Total trades row count changed on replay: first {total_count_1}, second {total_count_2}"
        )

    finally:
        # Clean up test rows
        await conn.execute(
            "DELETE FROM vigil.trades WHERE symbol = 'ZENITHSME' AND trade_id LIKE 'T-REPLAY-%';"
        )
        await conn.close()
