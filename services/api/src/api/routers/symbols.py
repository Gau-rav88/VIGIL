from __future__ import annotations

import datetime
import random
from typing import Any

from api.auth import User, require_roles
from api.deps import get_pool
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/symbols", tags=["symbols"])

LARGE_MID_SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "TATAMOTORS", "BHARTIARTL",
    "ITC", "SBIN", "LICI", "HINDUNILVR", "LT", "BAJFINANCE", "MARUTI", "SUNPHARMA",
    "TITAN", "KOTAKBANK", "ADANIENT", "AXISBANK", "NTPC", "ONGC", "POWERGRID",
    "TATASTEEL", "ULTRACEMCO", "M&M", "COALINDIA", "BAJAJFINSV", "WIPRO", "HCLTECH", "ACMESYSTEMS"
]

MICRO_SME_SYMBOLS = [
    "ZENITHSME", "MICROTECH", "ALPHASME", "SOLARIS", "NOVAPHARMA",
    "NEXUSSME", "PRISMIND", "VORTEXSME", "STELLARSME", "APEXSME"
]


@router.get("/heatmap")
async def get_symbols_heatmap(
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    open_cases = set()
    pool = get_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT DISTINCT symbol FROM vigil.cases WHERE status IN ('OPENED', 'PENDING_REVIEW', 'PUBLISHED');")
                for r in rows:
                    open_cases.add(r["symbol"])
        except Exception:
            pass

    tickers: list[dict[str, Any]] = []
    rng = random.Random(42)

    for sym in LARGE_MID_SYMBOLS:
        is_case = sym in open_cases
        base = round(rng.uniform(450, 3100), 2)
        mrs = round(rng.uniform(0.01, 0.12), 3) if not is_case else 0.88
        tickers.append({
            "symbol": sym,
            "tier": "LARGE_MID",
            "price": base,
            "change_pct": round(rng.uniform(-2.5, 3.2), 2),
            "volume_24h": rng.randint(450000, 3500000),
            "mrs": mrs,
            "hype": round(mrs * 40.0, 1),
            "volume_z": round(mrs * 2.5, 2),
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "MANIPULATION_DETECTED" if is_case else ("ELEVATED" if mrs > 0.4 else "NORMAL"),
            "flags": ["RING_DETECTED", "HYPE_BURST"] if is_case else []
        })

    for sym in MICRO_SME_SYMBOLS:
        is_case = sym in open_cases or sym == "ZENITHSME"
        base = round(rng.uniform(35, 180), 2)
        mrs = 0.94 if is_case else round(rng.uniform(0.04, 0.19), 3)
        flags = ["CIRCULAR_CYCLE", "CROSS_MODAL_SPIKE", "TELEGRAM_CTA"] if is_case else []
        tickers.append({
            "symbol": sym,
            "tier": "MICRO_SME",
            "price": base if not is_case else 142.50,
            "change_pct": round(rng.uniform(-3.5, 4.5), 2) if not is_case else 18.4,
            "volume_24h": rng.randint(80000, 420000) if not is_case else 1250000,
            "mrs": mrs,
            "hype": 88.5 if is_case else round(mrs * 50.0, 1),
            "volume_z": 4.8 if is_case else round(mrs * 2.0, 2),
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "MANIPULATION_DETECTED" if is_case else ("ELEVATED" if mrs > 0.4 else "NORMAL"),
            "flags": flags
        })

    return {"items": tickers, "total": len(tickers)}


@router.get("/{symbol}/series")
async def get_symbol_series(
    symbol: str,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    res: str = "5s",
    user: User = Depends(require_roles("investigator", "compliance_officer", "admin", "auditor_readonly")),
) -> dict[str, Any]:
    # Returns aligned series: bars, hype, l2_metrics, mrs
    base_time = datetime.datetime.now(datetime.timezone.utc)
    hype_series = []
    bars_series = []
    l2_metrics = []
    mrs_series = []

    price = 120.0
    for i in range(60):
        t = (base_time - datetime.timedelta(seconds=(60 - i) * 5)).isoformat()
        # Coordinated jump simulation near the end
        if i > 40:
            hype = min(95.0, 30.0 + (i - 40) * 3.2)
            vol = 45000 + (i - 40) * 12000
            price += 0.85
            mrs = min(0.98, 0.20 + (i - 40) * 0.04)
        else:
            hype = max(5.0, 20.0 + (i % 5) * 2.0)
            vol = 12000 + (i % 7) * 1500
            price += 0.05 * ((i % 3) - 1)
            mrs = 0.12

        hype_series.append({"t": t, "hype": round(hype, 1)})
        bars_series.append({
            "t": t,
            "open": round(price - 0.2, 2),
            "high": round(price + 0.4, 2),
            "low": round(price - 0.3, 2),
            "close": round(price, 2),
            "volume": vol,
        })
        l2_metrics.append({
            "t": t,
            "spread_bps": 4.5,
            "depth_ratio": 1.2,
            "imbalance": 0.65 if i > 40 else 0.05,
        })
        mrs_series.append({"t": t, "mrs": round(mrs, 3)})

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
