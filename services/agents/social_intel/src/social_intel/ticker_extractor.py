from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from vigil_common.symbols import normalize_symbol

MentionType = Literal["CASHTAG", "SYMBOL", "COMPANY_NAME", "ALIAS"]

FINANCIAL_CUES = {
    "buy", "sell", "holding", "hold", "target", "tgt", "cmp", "circuit",
    "upper", "lower", "multibagger", "breakout", "chart", "volume",
    "shares", "share", "stock", "stocks", "rally", "stoploss", "sl",
    "kharido", "lelo", "becho", "niklo", "paisa", "bhav", "rocket", "pump",
    "dump", "entry", "exit", "accumulator", "operator", "call", "jackpot",
}

AMBIGUOUS_TOKENS = {"ZEN", "SOLAR", "NOVA", "ACME", "HOLD", "ALL", "CALL", "PUMP"}


class TickerExtractor:
    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            p = Path(__file__).resolve()
            root = p.parents[4]
            for parent in p.parents:
                if (parent / "config").is_dir():
                    root = parent
                    break
            config_path = root / "config" / "ticker_aliases.yaml"
        self.config_path = Path(config_path)
        self.ticker_map: dict[str, dict[str, Any]] = {}
        self.alias_to_symbol: dict[str, tuple[str, MentionType, float]] = {}
        self._load_config()

    def _load_config(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self.ticker_map = data.get("aliases", {})

        # Populate alias lookups
        for symbol, info in self.ticker_map.items():
            sym_upper = symbol.upper()
            self.alias_to_symbol[sym_upper] = (sym_upper, "SYMBOL", 0.92)

            comp_name = info.get("company_name", "")
            if comp_name:
                self.alias_to_symbol[comp_name.upper()] = (sym_upper, "COMPANY_NAME", 0.90)

            for alias in info.get("aliases", []):
                alias_upper = alias.upper()
                if alias_upper != sym_upper:
                    conf = 0.82 if alias_upper in AMBIGUOUS_TOKENS else 0.88
                    self.alias_to_symbol[alias_upper] = (sym_upper, "ALIAS", conf)

        # Standard large-cap default tickers
        for std_sym in ["RELIANCE", "TCS", "INFY"]:
            if std_sym not in self.alias_to_symbol:
                self.alias_to_symbol[std_sym] = (std_sym, "SYMBOL", 0.92)

    def extract_tickers(
        self, text: str
    ) -> list[tuple[str, float, MentionType]]:
        """
        Extract tickers from text with per-mention confidence and mention type.
        Returns list of (symbol, confidence, mention_type).
        """
        results: dict[str, tuple[float, MentionType]] = {}
        text_upper = text.upper()
        words = set(re.findall(r"\b[A-Za-z0-9&._-]+\b", text.lower()))
        has_cue = bool(words & FINANCIAL_CUES)

        # 1. Match Cashtags ($SYMBOL) - highest confidence
        cashtags = re.findall(r"\$([A-Z0-9&._-]{1,24})\b", text)
        for tag in cashtags:
            norm = normalize_symbol(tag, has_cashtag=True, has_cue=has_cue)
            if norm:
                results[norm] = (0.95, "CASHTAG")
            else:
                sym_candidate = tag.upper()
                resolved = self.alias_to_symbol.get(sym_candidate, (sym_candidate, "CASHTAG", 0.95))
                results[resolved[0]] = (0.95, "CASHTAG")

        # 2. Match Company Names (case-insensitive substring)
        for alias, (symbol, mtype, conf) in self.alias_to_symbol.items():
            if mtype == "COMPANY_NAME":
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, text_upper):
                    norm = normalize_symbol(symbol, has_cue=has_cue) or symbol
                    if norm not in results or conf > results[norm][0]:
                        results[norm] = (conf, "COMPANY_NAME")

        # 3. Match Exact Symbols and Aliases with Ambiguity Rules
        for alias, (symbol, mtype, conf) in self.alias_to_symbol.items():
            if mtype in ("SYMBOL", "ALIAS"):
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, text_upper):
                    norm = normalize_symbol(alias, has_cue=has_cue)
                    if not norm:
                        continue
                    if norm not in results or conf > results[norm][0]:
                        results[norm] = (conf, mtype)

        return [(sym, conf, mtype) for sym, (conf, mtype) in results.items()]
