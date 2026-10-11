from __future__ import annotations

import collections
import os
from pathlib import Path

import yaml

from vigil_common.logging import get_logger

logger = get_logger("symbols")

# Metric counter for unmatched cashtags/symbols
UNMATCHED_SYMBOLS: dict[str, int] = collections.defaultdict(int)

_CANONICAL_ALIASES: dict[str, str] = {}
_AMBIGUOUS_TOKENS: set[str] = set()
_LOADED = False


def _find_aliases_path() -> Path | None:
    env_path = os.getenv("VIGIL_TICKER_ALIASES_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # Traverse upward from current file
    curr = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = curr / "config" / "ticker_aliases.yaml"
        if candidate.exists():
            return candidate
        curr = curr.parent

    # Check root cwd
    cwd_candidate = Path("config/ticker_aliases.yaml")
    if cwd_candidate.exists():
        return cwd_candidate

    return None


def load_instrument_aliases(path: Path | str | None = None) -> None:
    global _CANONICAL_ALIASES, _AMBIGUOUS_TOKENS, _LOADED

    file_path = Path(path) if path else _find_aliases_path()
    alias_map: dict[str, str] = {}
    ambiguous: set[str] = set()

    if file_path and file_path.exists():
        try:
            content = yaml.safe_load(file_path.read_text(encoding="utf-8"))
            if isinstance(content, dict):
                aliases_section = content.get("aliases", {})
                for canon, meta in aliases_section.items():
                    canon_clean = canon.strip().upper()
                    alias_map[canon_clean] = canon_clean
                    for alt in meta.get("aliases", []):
                        alt_clean = str(alt).strip().upper()
                        alias_map[alt_clean] = canon_clean

                ambig_section = content.get("ambiguous_tokens", [])
                for tok in ambig_section:
                    ambiguous.add(str(tok).strip().upper())
        except Exception as exc:
            logger.warning("Failed to load ticker_aliases.yaml, using defaults", error=str(exc))

    if not alias_map:
        # Built-in fallback
        defaults: dict[str, list[str]] = {
            "BTCUSDT": ["BTC", "BTCUSDT", "BITCOIN", "XBT"],
            "ETHUSDT": ["ETH", "ETHUSDT", "ETHEREUM"],
            "SOLUSDT": ["SOL", "SOLUSDT", "SOLANA"],
            "ZENITH": ["ZENITH", "ZENITH TECH", "ZEN"],
            "ACMESYSTEMS": ["ACME", "ACMESYS"],
            "NOVAPHARMA": ["NOVA", "NOVAPHARM"],
            "SOLARIS": ["SOLARIS", "SOLAR"],
            "RELIANCE": ["RELIANCE", "RIL"],
            "TCS": ["TCS"],
            "INFY": ["INFY", "INFOSYS"],
        }
        for canon, alts in defaults.items():
            for alt in alts:
                alias_map[alt] = canon
        ambiguous = {"SOL", "ZEN", "NOVA", "ACME"}

    _CANONICAL_ALIASES = alias_map
    _AMBIGUOUS_TOKENS = ambiguous
    _LOADED = True


def normalize_symbol(
    raw_token: str | None,
    has_cashtag: bool = False,
    has_cue: bool = False,
) -> str | None:
    """
    Normalizes a token/symbol string to its canonical instrument symbol.
    Never fuzzy-matches.
    Ambiguous tokens (e.g. 'SOL') require has_cashtag=True or has_cue=True.
    """
    if not raw_token:
        return None

    if not _LOADED:
        load_instrument_aliases()

    token = str(raw_token).strip()
    if token.startswith("$"):
        has_cashtag = True
        token = token[1:].strip()
    elif token.startswith("#"):
        token = token[1:].strip()

    token_upper = token.upper()
    if not token_upper:
        return None

    # Check if ambiguous short token without cashtag or cue
    if token_upper in _AMBIGUOUS_TOKENS and not (has_cashtag or has_cue):
        UNMATCHED_SYMBOLS[token_upper] += 1
        logger.debug("Ambiguous symbol rejected without cashtag or cue", token=token_upper)
        return None

    # Exact alias lookup
    canon = _CANONICAL_ALIASES.get(token_upper)
    if canon:
        return canon

    # Unmatched
    UNMATCHED_SYMBOLS[token_upper] += 1
    logger.debug("Symbol unmatched", token=token_upper)
    return None


def get_unmatched_symbols() -> dict[str, int]:
    return dict(UNMATCHED_SYMBOLS)


def reset_unmatched_symbols() -> None:
    UNMATCHED_SYMBOLS.clear()
