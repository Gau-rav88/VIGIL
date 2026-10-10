from __future__ import annotations

from pathlib import Path
from typing import Sequence

import scipy.stats as stats
import yaml

from attribution.models import LinkMethod, MethodScore


def load_attribution_weights() -> tuple[dict[str, float], dict[str, float]]:
    """Load method weights and thresholds from config/attribution_weights.yaml."""
    cfg_path = Path("config/attribution_weights.yaml")
    if not cfg_path.exists():
        root_path = Path(__file__).resolve().parents[5] / "config" / "attribution_weights.yaml"
        if root_path.exists():
            cfg_path = root_path

    default_weights = {
        "SHARED_KYC": 0.95,
        "SHARED_DEVICE": 0.90,
        "CIRCULAR_CYCLE": 0.85,
        "SYNCHRONIZED_ORDERS": 0.70,
        "SHARED_NETWORK": 0.60,
        "LATENCY_SIGNATURE": 0.50,
        "REACTION_LATENCY": 0.50,
        "BROKER_PATHWAY": 0.40,
    }
    default_thresholds = {
        "link_confidence": 0.60,
        "high_confidence": 0.80,
        "confirm_boost": 0.95,
        "max_cycle_length": 6.0,
        "reaction_p_thr": 0.01,
    }

    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            weights = data.get("weights", default_weights)
            thresholds = data.get("thresholds", default_thresholds)
            return weights, thresholds

    return default_weights, default_thresholds


class LinkMethodEvaluator:
    def __init__(
        self,
        weights: dict[str, float] | None = None,
        thresholds: dict[str, float] | None = None,
    ) -> None:
        loaded_w, loaded_t = load_attribution_weights()
        self.weights = weights or loaded_w
        self.thresholds = thresholds or loaded_t

    def get_weight(self, method: LinkMethod) -> float:
        return float(self.weights.get(method.value, 0.5))

    def eval_shared_kyc(
        self,
        kyc_a: dict[str, str | None],
        kyc_b: dict[str, str | None],
    ) -> MethodScore | None:
        """SHARED_KYC (w=0.95): s=1.0 if any KYC hash matches."""
        matched_keys: list[str] = []
        for key in ("phone_hash", "bank_hash", "addr_hash", "pan_hash"):
            val_a = kyc_a.get(key)
            val_b = kyc_b.get(key)
            if val_a and val_b and val_a == val_b:
                matched_keys.append(key)

        if matched_keys:
            return MethodScore(
                method=LinkMethod.SHARED_KYC,
                weight=self.get_weight(LinkMethod.SHARED_KYC),
                strength=1.0,
                details={"matched_keys": matched_keys},
            )
        return None

    def eval_shared_device(
        self,
        shared_devices: Sequence[str],
    ) -> MethodScore | None:
        """SHARED_DEVICE (w=0.90): s = min(1.0, 0.6 + 0.1 * shared_device_count)."""
        count = len(shared_devices)
        if count >= 1:
            strength = min(1.0, 0.6 + 0.1 * count)
            return MethodScore(
                method=LinkMethod.SHARED_DEVICE,
                weight=self.get_weight(LinkMethod.SHARED_DEVICE),
                strength=strength,
                details={"count": count, "devices": list(shared_devices)},
            )
        return None

    def eval_circular_cycle(
        self,
        cycles_together: int,
    ) -> MethodScore | None:
        """CIRCULAR_CYCLE (w=0.85): s = min(1.0, cycles_together / 3.0)."""
        if cycles_together >= 1:
            strength = min(1.0, cycles_together / 3.0)
            return MethodScore(
                method=LinkMethod.CIRCULAR_CYCLE,
                weight=self.get_weight(LinkMethod.CIRCULAR_CYCLE),
                strength=strength,
                details={"cycles_together": cycles_together},
            )
        return None

    def eval_synchronized_orders(
        self,
        best_p: float,
        co_orders: int,
    ) -> MethodScore | None:
        """SYNCHRONIZED_ORDERS (w=0.70): s = clip(1.0 - best_p * 100, 0.0, 1.0)."""
        if co_orders >= 1 and best_p <= 0.01:
            strength = max(0.0, min(1.0, 1.0 - best_p * 100.0))
            return MethodScore(
                method=LinkMethod.SYNCHRONIZED_ORDERS,
                weight=self.get_weight(LinkMethod.SYNCHRONIZED_ORDERS),
                strength=strength,
                details={"best_p": best_p, "co_orders": co_orders},
            )
        return None

    def eval_shared_network(
        self,
        ip_match: bool,
        same_asn: bool,
        same_gateway: bool,
    ) -> MethodScore | None:
        """
        SHARED_NETWORK (w=0.60):
        1.0 if same ip_hash; 0.5 if same ASN and same gateway_id / api_client_id.
        """
        if ip_match:
            return MethodScore(
                method=LinkMethod.SHARED_NETWORK,
                weight=self.get_weight(LinkMethod.SHARED_NETWORK),
                strength=1.0,
                details={"match_type": "SAME_IP"},
            )
        elif same_asn and same_gateway:
            return MethodScore(
                method=LinkMethod.SHARED_NETWORK,
                weight=self.get_weight(LinkMethod.SHARED_NETWORK),
                strength=0.5,
                details={"match_type": "SAME_ASN_AND_GATEWAY"},
            )
        return None

    def eval_latency_signature(
        self,
        latencies_a: Sequence[float],
        latencies_b: Sequence[float],
    ) -> MethodScore | None:
        """
        LATENCY_SIGNATURE (w=0.50):
        KS test on >= 50 samples each: s = min(1.0, p_ks / 0.5).
        """
        if len(latencies_a) >= 50 and len(latencies_b) >= 50:
            res = stats.ks_2samp(latencies_a, latencies_b)
            p_ks = float(res.pvalue)
            if p_ks > 0.05:  # Cannot reject null hypothesis that distributions are same
                strength = min(1.0, p_ks / 0.5)
                return MethodScore(
                    method=LinkMethod.LATENCY_SIGNATURE,
                    weight=self.get_weight(LinkMethod.LATENCY_SIGNATURE),
                    strength=strength,
                    details={"p_ks": p_ks, "statistic": float(res.statistic)},
                )
        return None

    def eval_reaction_latency(
        self,
        trader_latencies: Sequence[float],
        ref_latencies: Sequence[float],
    ) -> MethodScore | None:
        """
        REACTION_LATENCY (w=0.50):
        Mann-Whitney U test vs reference random reaction times:
        link if p < 0.01 and n >= 3. s = 1.0 - p.
        """
        if len(trader_latencies) >= 3 and len(ref_latencies) >= 20:
            # One-sided test: are trader reactions faster than reference?
            res = stats.mannwhitneyu(trader_latencies, ref_latencies, alternative="less")
            p_val = float(res.pvalue)
            p_thr = float(self.thresholds.get("reaction_p_thr", 0.01))
            if p_val < p_thr:
                strength = max(0.0, min(1.0, 1.0 - p_val))
                return MethodScore(
                    method=LinkMethod.REACTION_LATENCY,
                    weight=self.get_weight(LinkMethod.REACTION_LATENCY),
                    strength=strength,
                    details={"p_val": p_val, "samples": len(trader_latencies)},
                )
        return None

    def eval_broker_pathway(
        self,
        broker_a: str,
        gateway_a: str,
        share_a: float,
        broker_b: str,
        gateway_b: str,
        share_b: float,
    ) -> MethodScore | None:
        """BROKER_PATHWAY (w=0.40): 1.0 if both >= 80% share via same (broker, gateway)."""
        if (
            broker_a == broker_b
            and gateway_a == gateway_b
            and share_a >= 0.80
            and share_b >= 0.80
        ):
            return MethodScore(
                method=LinkMethod.BROKER_PATHWAY,
                weight=self.get_weight(LinkMethod.BROKER_PATHWAY),
                strength=1.0,
                details={
                    "broker": broker_a,
                    "gateway": gateway_a,
                    "share_a": share_a,
                    "share_b": share_b,
                },
            )
        return None
