from __future__ import annotations

import re
import unicodedata

# Common emojis in financial and pump social chatter
PUMP_EMOJIS = set("🚀📈🔥💎🙌💰💣⚡🎯🚨✨")

URL_REGEX = re.compile(r"https?://\S+|www\.\S+")
MENTION_REGEX = re.compile(r"@[\w_]+")


def normalize_text(text: str) -> str:
    """
    Perform Unicode NFKC normalization, strip URLs and generic mentions,
    while carefully preserving cashtags ($SYMBOL), prices, and financial symbols.
    """
    if not text:
        return ""

    # 1. Unicode NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)

    # 2. Strip URLs (save or drop)
    cleaned = URL_REGEX.sub(" ", normalized)

    # 3. Strip @user mentions (not cashtags which start with $)
    cleaned = MENTION_REGEX.sub(" ", cleaned)

    # 4. Collapse multiple whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def extract_emojis(text: str) -> list[str]:
    """
    Extract emoji characters from text for urgency/sentiment calculation.
    """
    return [c for c in text if c in PUMP_EMOJIS or unicodedata.category(c) == "So"]


def emoji_density(text: str) -> float:
    """
    Compute emoji density ratio (emojis per 100 characters).
    """
    if not text:
        return 0.0
    emojis = extract_emojis(text)
    return min(1.0, len(emojis) / 5.0)
