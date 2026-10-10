from __future__ import annotations

from typing import Sequence

from attribution.models import AccountPairLink, MethodScore


def calculate_pair_confidence(scores: Sequence[MethodScore]) -> float:
    r"""Compute pair confidence via noisy-OR: conf_ij = 1 - \prod_m (1 - w_m * s_m)."""
    if not scores:
        return 0.0

    prod = 1.0
    for s in scores:
        w_s = max(0.0, min(1.0, s.weight * s.strength))
        prod *= (1.0 - w_s)

    conf = 1.0 - prod
    return max(0.0, min(1.0, float(conf)))


def is_finding_link(confidence: float, threshold: float = 0.60) -> bool:
    """Guardrail G-2: links >= 0.60 are findings; below 0.60 are inferred-low leads."""
    return confidence >= threshold


def calculate_ring_score(
    pairs: Sequence[AccountPairLink],
    entity_volume_share: float,
    weights: dict[str, float],
) -> float:
    r"""
    Calculate ring score for an entity cluster:
    Let S_m = max over pairs in E of s_m.
    ring_score(E) = min(0.99, 1 - \prod_m (1 - w_m * S_m)) * min(1.0, 0.5 + 2 * entity_volume_share).
    """
    if not pairs:
        return 0.0

    # Collect max strength per method across all pairs in the entity
    max_strength: dict[str, float] = {}
    for p in pairs:
        for s in p.method_scores:
            m_key = s.method.value if hasattr(s.method, "value") else str(s.method)
            max_strength[m_key] = max(max_strength.get(m_key, 0.0), s.strength)

    # Compute noisy-OR over aggregated strengths
    prod = 1.0
    for m_key, S_m in max_strength.items():
        w_m = weights.get(m_key, 0.5)
        w_S = max(0.0, min(1.0, w_m * S_m))
        prod *= (1.0 - w_S)

    base = min(0.99, 1.0 - prod)
    volume_multiplier = min(1.0, 0.5 + 2.0 * max(0.0, entity_volume_share))
    ring_score = base * volume_multiplier
    return max(0.0, min(0.99, float(ring_score)))
