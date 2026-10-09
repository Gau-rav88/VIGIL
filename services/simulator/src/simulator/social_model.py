from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from vigil_common.models.social import SocialMessage

from simulator.ring import generate_id


@dataclass
class Channel:
    channel_id: str
    platform: str
    name: str
    visibility: str
    member_count: int
    is_pump: bool = False


class SocialModel:
    def __init__(
        self,
        rng: np.random.Generator,
        scenario_cfg: dict[str, Any] | None = None,
        symbols: list[str] | None = None,
    ) -> None:
        self.rng = rng
        self.scenario_cfg = scenario_cfg or {}
        self.symbols = symbols or ["ZENITHSME", "RELIANCE", "TCS", "INFY", "ACMESYSTEMS"]
        self.channels = self._init_channels()
        self.en_pump_templates = self._load_templates("telegram_pump_en.txt")
        self.hi_pump_templates = self._load_templates("telegram_pump_hinglish.txt")
        self.organic_templates = self._load_templates("organic_chatter.txt")
        self.pump_authors = [generate_id(self.rng, 22) for _ in range(4)]
        self.msg_seq = 0
        self.burst_active = False

    def _load_templates(self, filename: str) -> list[str]:
        path = Path(__file__).parent / "templates" / filename
        if not path.exists():
            return ["Discussion on {ticker}."]
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        return lines or ["Discussion on {ticker}."]

    def _init_channels(self) -> list[Channel]:
        channels: list[Channel] = [
            # 3 Pump channels
            Channel("tg-pump-elite", "telegram", "Elite Wealth Pumps", "public", 45000, is_pump=True),
            Channel("tg-jackpot-calls", "telegram", "Jackpot Stock Calls", "public", 62000, is_pump=True),
            Channel("tg-multibagger-insider", "telegram", "Multibagger Insider", "public", 38000, is_pump=True),
            # 22 Organic channels across platforms
            Channel("disc-retail-traders", "discord", "Retail Traders Hub", "public", 15400),
            Channel("disc-algo-lounge", "discord", "Algo & Quant Lounge", "public", 8900),
            Channel("disc-options-desk", "discord", "Options Desk Community", "public", 22000),
            Channel("reddit-dalalstreet", "reddit", "r/IndianStreetBets", "public", 185000),
            Channel("reddit-investing", "reddit", "r/IndiaInvestments", "public", 320000),
            Channel("reddit-pennystocks", "reddit", "r/PennyStocksIndia", "public", 45000),
            Channel("tg-market-pulse", "telegram", "Market Pulse Daily", "public", 85000),
            Channel("tg-nifty-banknifty", "telegram", "Nifty BankNifty Levels", "public", 95000),
            Channel("tg-value-investors", "telegram", "Value Investing India", "public", 28000),
            Channel("x-stock-talk", "x", "StockTalk Community", "public", 120000),
            Channel("x-dalal-buzz", "x", "Dalal Buzz", "public", 75000),
            Channel("x-chart-breakouts", "x", "Breakout Charts", "public", 64000),
            Channel("stocktwits-in", "stocktwits", "Stocktwits India Hub", "public", 51000),
            Channel("forum-traderji", "forum", "Traderji Community Forum", "public", 42000),
            Channel("disc-swing-setups", "discord", "Swing Trading Setups", "public", 11200),
            Channel("tg-macro-trends", "telegram", "Macro Trends & FX", "public", 19500),
            Channel("tg-ipo-alerts", "telegram", "IPO Grey Market Updates", "public", 140000),
            Channel("reddit-swingtraders", "reddit", "r/SwingTradersIndia", "public", 34000),
            Channel("x-market-movers", "x", "Market Movers Live", "public", 88000),
            Channel("stocktwits-sme", "stocktwits", "SME Stock Watch", "public", 18000),
            Channel("forum-moneycontrol", "forum", "Moneycontrol Message Board", "public", 95000),
            Channel("tg-derivatives-pro", "telegram", "Derivatives Pro Trading", "public", 31000),
        ]
        return channels

    def generate_step(
        self,
        sim_time_s: float,
        dt_s: float,
        current_iso_time: str,
    ) -> list[SocialMessage]:
        messages: list[SocialMessage] = []
        target_info = self.scenario_cfg.get("target", {})
        target_symbol = target_info.get("symbol", "ZENITHSME")
        target_price = target_info.get("base_price", 40.0) * 1.5

        social_cfg = self.scenario_cfg.get("social") or {}
        burst_cfg = social_cfg.get("burst")
        t0_s = social_cfg.get("t0_s", 300)

        # 1. Check if scenario pump burst is active
        in_burst = False
        if burst_cfg and t0_s is not None:
            burst_duration = burst_cfg.get("duration_s", 600)
            if t0_s <= sim_time_s < (t0_s + burst_duration):
                in_burst = True

        self.burst_active = in_burst

        # Burst generation
        if in_burst and burst_cfg:
            msgs_per_min = burst_cfg.get("msgs_per_min", 90)
            rate_per_sec = msgs_per_min / 60.0
            expected_msgs = rate_per_sec * dt_s
            num_burst = int(self.rng.poisson(expected_msgs))

            pump_channels = [c for c in self.channels if c.is_pump]
            near_dup_ratio = burst_cfg.get("near_dup_ratio", 0.5)
            last_dup_text: str | None = None

            for _ in range(num_burst):
                ch = pump_channels[self.rng.integers(0, len(pump_channels))]
                use_hinglish = self.rng.random() < 0.5
                templates = self.hi_pump_templates if use_hinglish else self.en_pump_templates

                if last_dup_text and self.rng.random() < near_dup_ratio:
                    text = last_dup_text
                else:
                    template = templates[self.rng.integers(0, len(templates))]
                    text = template.replace("{ticker}", target_symbol).replace("${ticker}", f"${target_symbol}")
                    text = text.replace("{target}", f"{target_price:.2f}")
                    text = text.replace("{time}", "14:30")
                    last_dup_text = text

                self.msg_seq += 1
                author_id = self.pump_authors[self.rng.integers(0, len(self.pump_authors))]
                raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

                msg = SocialMessage(
                    schema_version="1.0.0",
                    event_id=str(uuid.uuid5(uuid.NAMESPACE_OID, f"social:{ch.channel_id}:{self.msg_seq}")),
                    platform=ch.platform,  # type: ignore[arg-type]
                    channel_id=ch.channel_id,
                    channel_name=ch.name,
                    channel_visibility="public",
                    channel_member_count=ch.member_count,
                    message_id=f"M-{self.msg_seq:08d}",
                    author_id=author_id,
                    ts_posted=current_iso_time,
                    text=text,
                    lang="hi" if use_hinglish else "en",
                    urls=[],
                    media_sha256=[],
                    raw_sha256=raw_hash,
                    is_synthetic=True,
                    scenario_label=self.scenario_cfg.get("id"),
                )
                messages.append(msg)

        # 2. Ambient organic chatter (across all channels)
        ambient_rate_per_sec = 0.5  # ~30 organic messages per minute
        ambient_expected = ambient_rate_per_sec * dt_s
        num_organic = int(self.rng.poisson(ambient_expected))

        organic_channels = [c for c in self.channels if not c.is_pump]
        for _ in range(num_organic):
            ch = organic_channels[self.rng.integers(0, len(organic_channels))]
            sym = self.symbols[self.rng.integers(0, len(self.symbols))]
            template = self.organic_templates[self.rng.integers(0, len(self.organic_templates))]
            text = template.replace("{ticker}", sym).replace("${ticker}", f"${sym}")
            self.msg_seq += 1
            author_id = generate_id(self.rng, 22)
            raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            msg = SocialMessage(
                schema_version="1.0.0",
                event_id=str(uuid.uuid5(uuid.NAMESPACE_OID, f"social:{ch.channel_id}:{self.msg_seq}")),
                platform=ch.platform,  # type: ignore[arg-type]
                channel_id=ch.channel_id,
                channel_name=ch.name,
                channel_visibility="public",
                channel_member_count=ch.member_count,
                message_id=f"M-{self.msg_seq:08d}",
                author_id=author_id,
                ts_posted=current_iso_time,
                text=text,
                lang="en",
                urls=[],
                media_sha256=[],
                raw_sha256=raw_hash,
                is_synthetic=True,
                scenario_label=None,
            )
            messages.append(msg)

        return messages
