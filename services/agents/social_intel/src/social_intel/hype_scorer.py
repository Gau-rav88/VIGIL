from __future__ import annotations

import collections
import datetime
import hashlib
import math
import uuid
from pathlib import Path
from typing import Any

import yaml
from vigil_common.logging import get_logger
from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

logger = get_logger("hype_scorer")


def sigmoid(x: float) -> float:
    # Stable sigmoid
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)


class TickerHypeState:
    def __init__(self, symbol: str, ewma_alpha: float = 0.02) -> None:
        self.symbol = symbol
        self.ewma_alpha = ewma_alpha

        # Sliding window buffer: list of signal dicts
        self.window: collections.deque[dict[str, Any]] = collections.deque()

        # EWMA statistics for 5s message arrival rate (baseline horizon ≈ 1h)
        self.rate_ewma_mean = 0.3
        self.rate_ewma_var = 0.25

        # EWMA statistics for unique authors
        self.auth_ewma_mean = 0.5
        self.auth_ewma_var = 0.25

        # Burst tracking
        self.burst_consecutive_s = 0.0
        self.last_burst_emitted_ts = 0.0
        self.last_step_ts = 0.0
        self.last_ewma_ts = 0.0
        self.current_hype_score = 0.0


class HypeScorer:
    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            p = Path(__file__).resolve()
            root = p.parents[4]
            for parent in p.parents:
                if (parent / "config").is_dir():
                    root = parent
                    break
            config_path = root / "config" / "hype_weights.yaml"
        self.config_path = Path(config_path)

        # Default weights and thresholds from ARCHITECTURE.md §7.2
        self.weights = {
            "f_rate": 0.25,
            "f_auth": 0.15,
            "f_cta": 0.20,
            "f_dup": 0.15,
            "f_urg": 0.10,
            "f_xch": 0.15,
        }
        self.window_s = 60.0
        self.step_s = 5.0
        self.min_messages = 5
        self.ewma_alpha = 0.02
        self.burst_threshold = 70.0
        self.burst_sustain_s = 30.0

        self._load_config()
        self.states: dict[str, TickerHypeState] = {}
        self.config_hash = hashlib.sha256(b"hype_scorer_v1.0").hexdigest()
        self.reported_campaign_clusters: set[str] = set()

    def _load_config(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if "weights" in data:
                    self.weights.update(data["weights"])
                if "thresholds" in data:
                    thr = data["thresholds"]
                    self.window_s = float(thr.get("window_s", self.window_s))
                    self.step_s = float(thr.get("step_s", self.step_s))
                    self.min_messages = int(thr.get("min_messages", self.min_messages))
                    self.ewma_alpha = float(thr.get("ewma_alpha", self.ewma_alpha))
                    self.burst_threshold = float(thr.get("burst_threshold", self.burst_threshold))
                    self.burst_sustain_s = float(thr.get("burst_sustain_s", self.burst_sustain_s))

    def _get_state(self, symbol: str) -> TickerHypeState:
        if symbol not in self.states:
            self.states[symbol] = TickerHypeState(symbol, self.ewma_alpha)
        return self.states[symbol]

    def add_signal(self, signal: dict[str, Any]) -> None:
        """
        Buffer a normalized SocialSignal for hype score calculation.
        """
        ticker = signal.get("ticker", "").upper()
        if not ticker:
            return

        conf = float(signal.get("ticker_confidence", 0.0))
        if conf < 0.6:
            return

        st = self._get_state(ticker)
        ts_val = signal.get("ts_numeric")
        if ts_val is None:
            ts_str = signal.get("ts_posted")
            try:
                dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))  # type: ignore[union-attr]
                ts_val = dt.timestamp()
            except Exception:
                ts_val = datetime.datetime.now(datetime.timezone.utc).timestamp()
            signal["ts_numeric"] = ts_val

        st.window.append(signal)

    def evaluate_step(
        self,
        symbol: str,
        now_ts: float | None = None,
    ) -> tuple[dict[str, Any], list[AnomalyEvent]]:
        """
        Calculates hype_score for a ticker at the current step and checks for anomalies.
        Returns (hype_metrics_dict, list_of_anomaly_events).
        """
        st = self._get_state(symbol)
        if now_ts is not None:
            now = now_ts
        elif st.window:
            now = float(st.window[-1]["ts_numeric"])
        else:
            now = datetime.datetime.now(datetime.timezone.utc).timestamp()

        # 1. Prune signals older than window W = 60s
        cutoff = now - self.window_s
        while st.window and st.window[0]["ts_numeric"] < cutoff:
            st.window.popleft()

        recent = list(st.window)
        n = len(recent)

        # Count messages in the last step interval (e.g. 5s)
        last_5s_cutoff = now - self.step_s
        count_5s = sum(1 for s in recent if s["ts_numeric"] >= last_5s_cutoff)

        # 2. Update EWMA for baseline arrival rate and authors (step 5s, baseline horizon ≈ 1h)
        if st.last_ewma_ts == 0.0:
            st.last_ewma_ts = now
        elif (now - st.last_ewma_ts) >= self.step_s:
            steps = int((now - st.last_ewma_ts) // self.step_s)
            st.last_ewma_ts += steps * self.step_s
            alpha = min(0.1, 0.002 * steps)
            delta_rate = count_5s - st.rate_ewma_mean
            st.rate_ewma_mean += alpha * min(2.0, max(-2.0, delta_rate))
            st.rate_ewma_var = max(0.25, (1 - alpha) * st.rate_ewma_var + alpha * min(1.0, delta_rate**2))

            unique_authors = len({s.get("author_id") for s in recent if s.get("author_id")})
            delta_auth = unique_authors - st.auth_ewma_mean
            st.auth_ewma_mean += alpha * min(2.0, max(-2.0, delta_auth))
            st.auth_ewma_var = max(0.25, (1 - alpha) * st.auth_ewma_var + alpha * min(1.0, delta_auth**2))

        sigma_rate = max(0.5, math.sqrt(st.rate_ewma_var))
        z_rate = (count_5s - st.rate_ewma_mean) / sigma_rate
        f_rate = sigmoid((z_rate - 3.0) / 1.0)

        # 3. Unique authors and z_auth
        unique_authors = len({s.get("author_id") for s in recent if s.get("author_id")})
        sigma_auth = max(0.5, math.sqrt(st.auth_ewma_var))
        z_auth = (unique_authors - st.auth_ewma_mean) / sigma_auth
        f_auth = sigmoid((z_auth - 3.0) / 1.0)

        # 4. CTA Buy Call / Pump Confidence factor
        if n > 0:
            cta_sum = sum(
                float(s.get("cta_confidence", 0.8))
                for s in recent
                if s.get("cta_class") in ("BUY_CALL", "HOLD_PUMP", "TARGET_PRICE", "COORDINATION_TIMING")
            )
            f_cta = cta_sum / n
        else:
            f_cta = 0.0

        # 5. Near-duplicate cluster factor (size >= 3)
        dup_msgs = sum(
            1 for s in recent
            if s.get("near_dup_cluster_size", 0) >= 3 or s.get("is_dup", False)
        )
        f_dup = (dup_msgs / n) if n > 0 else 0.0

        # 6. Mean urgency
        f_urg = (sum(float(s.get("urgency", 0.0)) for s in recent) / n) if n > 0 else 0.0

        # 7. Cross-channel factor
        distinct_channels = len({s.get("channel_id") for s in recent if s.get("channel_id")})
        f_xch = min(1.0, max(0.0, (distinct_channels - 1) / 3.0))

        # Linear combination
        raw_hype = 100.0 * (
            self.weights["f_rate"] * f_rate
            + self.weights["f_auth"] * f_auth
            + self.weights["f_cta"] * f_cta
            + self.weights["f_dup"] * f_dup
            + self.weights["f_urg"] * f_urg
            + self.weights["f_xch"] * f_xch
        )

        # Small sample cap: if N < 5, cap hype_score = min(hype_score, 20.0)
        if n < self.min_messages:
            hype_score = min(raw_hype, 20.0)
        else:
            hype_score = raw_hype

        st.current_hype_score = hype_score

        metrics = {
            "ts": datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).isoformat(),
            "ticker": symbol,
            "hype_score": round(hype_score, 2),
            "f_rate": round(f_rate, 4),
            "f_auth": round(f_auth, 4),
            "f_cta": round(f_cta, 4),
            "f_dup": round(f_dup, 4),
            "f_urg": round(f_urg, 4),
            "f_xch": round(f_xch, 4),
            "msg_count": n,
            "unique_authors": unique_authors,
            "channels": distinct_channels,
        }

        # 8. Check Anomaly Triggers
        anomalies: list[AnomalyEvent] = []

        # Check HYPE_BURST: hype_score >= 70 continuously for >= 30s
        if hype_score >= self.burst_threshold:
            dt = (now - st.last_step_ts) if st.last_step_ts > 0 else self.step_s
            if dt > 15.0:
                st.burst_consecutive_s = min(dt, self.step_s)
            else:
                st.burst_consecutive_s += dt
            if st.burst_consecutive_s >= self.burst_sustain_s:
                # Fire anomaly if not recently fired (cooldown 60s)
                if (now - st.last_burst_emitted_ts) >= 60.0:
                    st.last_burst_emitted_ts = now
                    now_iso: str = str(metrics["ts"])
                    start_iso = datetime.datetime.fromtimestamp(now - 60.0, tz=datetime.timezone.utc).isoformat()

                    evidence = [
                        EvidenceRef(kind="social_message_id", ref=s.get("message_id", "M-00000000"))
                        for s in recent[:10] if s.get("message_id")
                    ] or [EvidenceRef(kind="social_message_id", ref="M-00000001")]

                    burst_anom = AnomalyEvent(
                        schema_version="1.0.0",
                        anomaly_id=str(uuid.uuid4()),
                        type="HYPE_BURST",
                        source_agent="social_intel",
                        symbol=symbol,
                        window_start=start_iso,
                        window_end=now_iso,
                        score=min(1.0, hype_score / 100.0),
                        severity="CRITICAL" if hype_score >= 85.0 else "HIGH",
                        metrics={
                            "hype_score": round(hype_score, 2),
                            "sustained_duration_s": round(st.burst_consecutive_s, 1),
                            "f_rate": round(f_rate, 2),
                            "f_cta": round(f_cta, 2),
                            "f_dup": round(f_dup, 2),
                            "messages_in_window": n,
                        },
                        participants=list({s.get("author_id", "") for s in recent if s.get("author_id")})[:10],
                        evidence_refs=evidence,
                        detector_version="1.0.0",
                        config_hash=self.config_hash,
                        detected_at=now_iso,
                    )
                    anomalies.append(burst_anom)
        else:
            st.burst_consecutive_s = 0.0

        st.last_step_ts = now
        return metrics, anomalies

    def check_near_duplicate_campaign(
        self,
        cluster_id: str,
        cluster_stats: dict[str, Any],
        symbol: str,
        now_ts: float | None = None,
    ) -> AnomalyEvent | None:
        """
        Check NEAR_DUPLICATE_CAMPAIGN: cluster with >= 5 messages from >= 3 distinct authors
        in >= 2 channels within 5 min (ARCHITECTURE.md §7.2).
        """
        if cluster_id in self.reported_campaign_clusters:
            return None

        count = cluster_stats.get("count", 0)
        authors = cluster_stats.get("unique_authors", 0)
        channels = cluster_stats.get("unique_channels", 0)
        duration_s = cluster_stats.get("duration_s", 0.0)

        if count >= 5 and authors >= 3 and channels >= 2 and duration_s <= 300.0:
            self.reported_campaign_clusters.add(cluster_id)
            now = now_ts if now_ts is not None else datetime.datetime.now(datetime.timezone.utc).timestamp()
            now_iso = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).isoformat()
            start_iso = datetime.datetime.fromtimestamp(now - duration_s, tz=datetime.timezone.utc).isoformat()

            return AnomalyEvent(
                schema_version="1.0.0",
                anomaly_id=str(uuid.uuid4()),
                type="NEAR_DUPLICATE_CAMPAIGN",
                source_agent="social_intel",
                symbol=symbol,
                window_start=start_iso,
                window_end=now_iso,
                score=min(1.0, 0.7 + 0.05 * count),
                severity="HIGH",
                metrics={
                    "cluster_id": cluster_id,
                    "message_count": count,
                    "unique_authors": authors,
                    "unique_channels": channels,
                    "duration_s": round(duration_s, 1),
                },
                participants=[],
                evidence_refs=[EvidenceRef(kind="social_message_id", ref=cluster_id)],
                detector_version="1.0.0",
                config_hash=self.config_hash,
                detected_at=now_iso,
            )

        return None
