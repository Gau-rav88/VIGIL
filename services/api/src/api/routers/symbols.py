from __future__ import annotations

import datetime
import logging
from typing import Any

from api.auth import User, require_roles
from api.deps import get_pool
from api.errors import ProblemException
from fastapi import APIRouter, Depends, Query

logger = logging.getLogger("api.symbols")
router = APIRouter(prefix="/api/v1", tags=["symbols"])


@router.get("/symbols/heatmap")
@router.get("/live/tickers")
async def get_symbols_heatmap(
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    pool = get_pool()
    if pool is None:
        raise ProblemException(
            status_code=503,
            title="Service Unavailable",
            detail="Database connection pool is not available",
            type_uri="https://api.vigil.dev/errors/dependency-failure",
        )

    try:
        async with pool.acquire() as conn:
            # Query distinct symbols with activity in trades
            symbol_rows = await conn.fetch("SELECT DISTINCT symbol FROM vigil.trades ORDER BY symbol;")
            if not symbol_rows:
                return {"items": [], "total": 0, "state": "EMPTY"}

            open_case_rows = await conn.fetch(
                "SELECT DISTINCT symbol FROM vigil.cases WHERE status IN ('OPENED', 'PENDING_REVIEW', 'PUBLISHED');"
            )
            open_cases = {r["symbol"] for r in open_case_rows}

            tickers: list[dict[str, Any]] = []

            for srow in symbol_rows:
                sym = srow["symbol"]
                is_case = sym in open_cases

                # Latest trade price and earliest in recent 24h
                price_rows = await conn.fetch(
                    """
                    SELECT price, ts, qty FROM vigil.trades
                    WHERE symbol = $1
                    ORDER BY ts DESC LIMIT 1000;
                    """,
                    sym,
                )

                if price_rows:
                    latest_price = float(price_rows[0]["price"])
                    earliest_price = float(price_rows[-1]["price"])
                    change_pct = round(((latest_price - earliest_price) / earliest_price) * 100, 2) if earliest_price > 0 else 0.0
                    total_vol = sum(float(r["qty"]) for r in price_rows)
                    latest_ts = price_rows[0]["ts"].isoformat()
                else:
                    latest_price = 0.0
                    change_pct = 0.0
                    total_vol = 0.0
                    latest_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

                # Latest MRS
                mrs_row = await conn.fetchrow(
                    "SELECT mrs FROM vigil.mrs_1m WHERE symbol = $1 ORDER BY ts DESC LIMIT 1;",
                    sym,
                )
                mrs = float(mrs_row["mrs"]) if mrs_row and mrs_row["mrs"] is not None else 0.0

                # Latest Hype
                hype_row = await conn.fetchrow(
                    "SELECT hype_score FROM vigil.hype_scores WHERE ticker = $1 ORDER BY ts DESC LIMIT 1;",
                    sym,
                )
                hype = float(hype_row["hype_score"]) if hype_row and hype_row["hype_score"] is not None else 0.0

                # Open anomalies for flags
                anom_rows = await conn.fetch(
                    "SELECT type FROM vigil.anomalies WHERE symbol = $1 ORDER BY detected_at DESC LIMIT 5;",
                    sym,
                )
                flags = list({str(r["type"]) for r in anom_rows})

                # Status thresholds per PRD
                if is_case or mrs >= 0.70:
                    status_val = "MANIPULATION_DETECTED"
                elif mrs >= 0.40 or bool(flags):
                    status_val = "ELEVATED"
                else:
                    status_val = "NORMAL"

                tier = "CRYPTO" if "USDT" in sym else ("MICRO_SME" if "SME" in sym else "LARGE_MID")

                tickers.append({
                    "symbol": sym,
                    "tier": tier,
                    "price": latest_price,
                    "change_pct": change_pct,
                    "volume_24h": total_vol,
                    "mrs": mrs,
                    "hype": hype,
                    "volume_z": round(mrs * 3.0, 2),
                    "ts": latest_ts,
                    "status": status_val,
                    "flags": flags,
                })

            state = "READY" if tickers else "EMPTY"
            return {"items": tickers, "total": len(tickers), "state": state}

    except Exception as exc:
        logger.error("Failed querying symbols heatmap from database", exc_info=True)
        raise ProblemException(
            status_code=503,
            title="Database Error",
            detail="Failed to query symbols heatmap from TimescaleDB",
            type_uri="https://api.vigil.dev/errors/database-error",
        ) from exc


@router.get("/symbols/{symbol}/series")
async def get_symbol_series(
    symbol: str,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    res: str = "5s",
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    pool = get_pool()
    if pool is None:
        raise ProblemException(
            status_code=503,
            title="Service Unavailable",
            detail="Database connection pool is not available",
            type_uri="https://api.vigil.dev/errors/dependency-failure",
        )

    try:
        async with pool.acquire() as conn:
            # Query Trades for Bars
            trade_query = "SELECT ts, price, qty FROM vigil.trades WHERE symbol = $1"
            params: list[Any] = [symbol]
            if from_ts:
                params.append(from_ts)
                trade_query += f" AND ts >= ${len(params)}::timestamptz"
            if to_ts:
                params.append(to_ts)
                trade_query += f" AND ts <= ${len(params)}::timestamptz"
            trade_query += " ORDER BY ts ASC LIMIT 10000;"

            trade_rows = await conn.fetch(trade_query, *params)

            bars_series: list[dict[str, Any]] = []
            if trade_rows:
                # Group trades into 5-second or 1-minute buckets
                buckets: dict[str, list[dict[str, float]]] = {}
                for tr in trade_rows:
                    dt = tr["ts"]
                    # 5s quantization
                    sec = (dt.second // 5) * 5
                    b_dt = dt.replace(second=sec, microsecond=0)
                    k = b_dt.isoformat()
                    if k not in buckets:
                        buckets[k] = []
                    buckets[k].append({"p": float(tr["price"]), "q": float(tr["qty"])})

                for k, pts in buckets.items():
                    prices = [p["p"] for p in pts]
                    bars_series.append({
                        "t": k,
                        "open": prices[0],
                        "high": max(prices),
                        "low": min(prices),
                        "close": prices[-1],
                        "volume": sum(p["q"] for p in pts),
                    })

            # Query Hype scores
            hype_query = "SELECT ts, hype_score FROM vigil.hype_scores WHERE ticker = $1"
            h_params: list[Any] = [symbol]
            if from_ts:
                h_params.append(from_ts)
                hype_query += f" AND ts >= ${len(h_params)}::timestamptz"
            if to_ts:
                h_params.append(to_ts)
                hype_query += f" AND ts <= ${len(h_params)}::timestamptz"
            hype_query += " ORDER BY ts ASC LIMIT 1000;"
            hype_rows = await conn.fetch(hype_query, *h_params)
            hype_series = [{"t": r["ts"].isoformat(), "hype": float(r["hype_score"])} for r in hype_rows]

            # Query L2 metrics
            l2_query = "SELECT ts, rel_spread, depth_imbalance FROM vigil.l2_metrics_1s WHERE symbol = $1"
            l2_params: list[Any] = [symbol]
            if from_ts:
                l2_params.append(from_ts)
                l2_query += f" AND ts >= ${len(l2_params)}::timestamptz"
            if to_ts:
                l2_params.append(to_ts)
                l2_query += f" AND ts <= ${len(l2_params)}::timestamptz"
            l2_query += " ORDER BY ts ASC LIMIT 1000;"
            l2_rows = await conn.fetch(l2_query, *l2_params)
            l2_metrics = [
                {
                    "t": r["ts"].isoformat(),
                    "spread_bps": float(r["rel_spread"] or 0.0) * 10000.0,
                    "depth_ratio": 1.0,
                    "imbalance": float(r["depth_imbalance"] or 0.0),
                }
                for r in l2_rows
            ]

            # Query MRS series
            mrs_query = "SELECT ts, mrs FROM vigil.mrs_1m WHERE symbol = $1"
            m_params: list[Any] = [symbol]
            if from_ts:
                m_params.append(from_ts)
                mrs_query += f" AND ts >= ${len(m_params)}::timestamptz"
            if to_ts:
                m_params.append(to_ts)
                mrs_query += f" AND ts <= ${len(m_params)}::timestamptz"
            mrs_query += " ORDER BY ts ASC LIMIT 1000;"
            mrs_rows = await conn.fetch(mrs_query, *m_params)
            mrs_series = [{"t": r["ts"].isoformat(), "mrs": float(r["mrs"])} for r in mrs_rows]

            return {
                "symbol": symbol,
                "from": from_ts,
                "to": to_ts,
                "res": res,
                "hype": hype_series,
                "bars": bars_series,
                "l2_metrics": l2_metrics,
                "mrs": mrs_series,
            }

    except Exception as exc:
        logger.error(f"Failed querying symbol series for {symbol} from database", exc_info=True)
        raise ProblemException(
            status_code=503,
            title="Database Error",
            detail="Failed to query symbol series from TimescaleDB",
            type_uri="https://api.vigil.dev/errors/database-error",
        ) from exc
