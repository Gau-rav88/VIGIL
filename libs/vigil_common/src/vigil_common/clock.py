from __future__ import annotations

import datetime
import os
from typing import Any

from vigil_common.logging import get_logger

logger = get_logger("clock")


def get_clock_mode() -> str:
    return os.getenv("CLOCK_MODE", "event").strip().lower()


async def get_analysis_time(
    symbol: str | None = None,
    redis_client: Any = None,
    db_conn: Any = None,
) -> float:
    """
    Returns current analysis time in seconds since epoch.
    - If CLOCK_MODE == "wall": returns current wall clock time (for live Binance).
    - If CLOCK_MODE == "event": returns the latest watermark for the symbol
      (max ts_exchange for trades or max ts of hype scores) from Redis or TimescaleDB.
      Falls back to global watermark, or wall clock if no event data exists yet.
    """
    mode = get_clock_mode()
    if mode == "wall":
        return datetime.datetime.now(datetime.timezone.utc).timestamp()

    # 1. Event mode: query Redis watermark maintained by stream_sink
    if redis_client:
        try:
            val = None
            if symbol and symbol != "UNKNOWN":
                val = await redis_client.get(f"watermark:{symbol}")
            if not val:
                val = await redis_client.get("watermark:global")
            if val:
                ts_str = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                return float(ts_str)
        except Exception as exc:
            logger.debug("Failed to read watermark from Redis", symbol=symbol, error=str(exc))

    # 2. Event mode fallback: query TimescaleDB max(ts)
    if db_conn:
        try:
            if symbol and symbol != "UNKNOWN":
                row = await db_conn.fetchrow(
                    "SELECT max(ts) as max_ts FROM vigil.trades WHERE symbol = $1",
                    symbol,
                )
            else:
                row = await db_conn.fetchrow("SELECT max(ts) as max_ts FROM vigil.trades")

            if row and row["max_ts"]:
                max_dt = row["max_ts"]
                if isinstance(max_dt, datetime.datetime):
                    return max_dt.timestamp()
        except Exception as exc:
            logger.debug("Failed to query max(ts) from DB", symbol=symbol, error=str(exc))

    return datetime.datetime.now(datetime.timezone.utc).timestamp()


async def get_analysis_datetime(
    symbol: str | None = None,
    redis_client: Any = None,
    db_conn: Any = None,
) -> datetime.datetime:
    ts = await get_analysis_time(symbol=symbol, redis_client=redis_client, db_conn=db_conn)
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
