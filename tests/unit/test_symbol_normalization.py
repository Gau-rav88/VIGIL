from __future__ import annotations

from vigil_common.symbols import (
    get_unmatched_symbols,
    normalize_symbol,
    reset_unmatched_symbols,
)


def test_symbol_normalization_table() -> None:
    reset_unmatched_symbols()

    # Direct canonical and aliases for BTC
    assert normalize_symbol("BTCUSDT") == "BTCUSDT"
    assert normalize_symbol("BTC") == "BTCUSDT"
    assert normalize_symbol("$BTC") == "BTCUSDT"
    assert normalize_symbol("bitcoin") == "BTCUSDT"
    assert normalize_symbol("XBT") == "BTCUSDT"

    # ETH
    assert normalize_symbol("ETHUSDT") == "ETHUSDT"
    assert normalize_symbol("ETH") == "ETHUSDT"
    assert normalize_symbol("$ETH") == "ETHUSDT"
    assert normalize_symbol("ethereum") == "ETHUSDT"

    # Synthetic symbols
    assert normalize_symbol("ZENITHSME") == "ZENITHSME"
    assert normalize_symbol("$ZENITH") == "ZENITHSME"
    assert normalize_symbol("ACMESYSTEMS") == "ACMESYSTEMS"


def test_ambiguous_tokens_require_cashtag_or_cue() -> None:
    # "SOL" alone is ambiguous
    assert normalize_symbol("SOL") is None
    assert normalize_symbol("sol") is None

    # "SOL" with cashtag or cue
    assert normalize_symbol("$SOL") == "SOLUSDT"
    assert normalize_symbol("SOL", has_cashtag=True) == "SOLUSDT"
    assert normalize_symbol("SOL", has_cue=True) == "SOLUSDT"
    assert normalize_symbol("SOLANA") == "SOLUSDT"


def test_unmatched_symbols_and_no_fuzzy_matching() -> None:
    reset_unmatched_symbols()

    # Unrelated tokens
    assert normalize_symbol("APPLE") is None
    assert normalize_symbol("XYZFOOBAR") is None

    # Never fuzzy match
    assert normalize_symbol("BTCC") is None
    assert normalize_symbol("ETHH") is None

    unmatched = get_unmatched_symbols()
    assert "APPLE" in unmatched
    assert "XYZFOOBAR" in unmatched
    assert "BTCC" in unmatched
