from __future__ import annotations

import collections
import datetime
import hashlib
import uuid
from typing import Any

from vigil_common.logging import get_logger
from vigil_common.models.anomaly import AnomalyEvent
from vigil_common.models.social import ParserMetadata, SocialSignal

from social_intel.cta_classifier import CtaClassifier
from social_intel.hype_scorer import HypeScorer
from social_intel.near_dup import MinHashLSH
from social_intel.normalization import normalize_text
from social_intel.ticker_extractor import TickerExtractor

logger = get_logger("social_intel_engine")


class SocialIntelEngine:
    def __init__(self) -> None:
        self.ticker_extractor = TickerExtractor()
        self.cta_classifier = CtaClassifier()
        self.lsh = MinHashLSH()
        self.hype_scorer = HypeScorer()
        self.signals_history: list[dict[str, Any]] = []

    def process_message(
        self,
        msg: dict[str, Any],
        now_ts: float | None = None,
    ) -> tuple[list[SocialSignal], list[AnomalyEvent], list[dict[str, Any]]]:
        """
        Process a raw SocialMessage into SocialSignals, update hype buffers,
        and detect any immediate anomalies (HYPE_BURST or NEAR_DUPLICATE_CAMPAIGN).
        Returns (signals, anomalies, hype_records).
        """
        raw_text = msg.get("text", "")
        if not raw_text:
            return [], [], []

        norm_text = normalize_text(raw_text)
        author_id = msg.get("author_id", "unknown")
        channel_id = msg.get("channel_id", "default")
        msg_id = msg.get("message_id", str(uuid.uuid4()))
        platform = msg.get("platform", "telegram")
        ts_posted = msg.get("ts_posted", datetime.datetime.now(datetime.timezone.utc).isoformat())
        raw_sha256 = msg.get("raw_sha256", hashlib.sha256(raw_text.encode("utf-8")).hexdigest())

        if now_ts is None:
            try:
                dt_post = datetime.datetime.fromisoformat(ts_posted.replace("Z", "+00:00"))
                now_ts = dt_post.timestamp()
            except Exception:
                now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()

        # 1. Near-duplicate LSH clustering (FR-SOC-05, P3-T07)
        cluster_id, cluster_size = self.lsh.insert_and_cluster(
            msg_id=msg_id,
            text=norm_text,
            author_id=author_id,
            channel_id=channel_id,
            ts=now_ts,
        )

        # 2. Extract tickers (FR-SOC-03, P3-T04)
        extracted_tickers = self.ticker_extractor.extract_tickers(norm_text)
        if not extracted_tickers:
            # Ambiguous or no ticker mentioned
            return [], [], []

        # 3. Classify CTA, Urgency, Target Price, Timing (FR-SOC-04, P3-T05)
        cta_res = self.cta_classifier.classify_fallback(norm_text)

        signals: list[SocialSignal] = []
        anomalies: list[AnomalyEvent] = []
        hype_records: list[dict[str, Any]] = []

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for symbol, conf, mention_type in extracted_tickers:
            # Build SocialSignal
            sig = SocialSignal(
                schema_version="1.0.0",
                signal_id=str(uuid.uuid4()),
                message_event_id=msg.get("event_id", str(uuid.uuid4())),
                platform=platform,
                channel_id=channel_id,
                author_id=author_id,
                ts_posted=ts_posted,
                ts_processed=now_iso,
                ticker=symbol,
                ticker_confidence=round(conf, 2),
                mention_type=mention_type,
                cta_class=cta_res["cta_class"],
                cta_confidence=cta_res["cta_confidence"],
                target_price=cta_res["target_price"],
                scheduled_action_time=cta_res["scheduled_action_time"],
                urgency=cta_res["urgency"],
                sentiment=cta_res["sentiment"],
                near_dup_cluster_id=cluster_id if cluster_size >= 2 else None,
                forward_cascade_depth=msg.get("forward_cascade_depth", 0),
                raw_sha256=raw_sha256,
                parser=ParserMetadata(
                    mode=cta_res["parser_mode"],
                    version="1.0.0",
                    prompt_sha256=cta_res.get("prompt_sha256"),
                    response_sha256=cta_res.get("response_sha256"),
                ),
            )
            signals.append(sig)

            # 4. Add to HypeScorer buffer
            sig_dict = sig.model_dump()
            sig_dict["near_dup_cluster_size"] = cluster_size
            sig_dict["message_id"] = msg_id
            if now_ts is not None:
                sig_dict["ts_numeric"] = now_ts
            self.hype_scorer.add_signal(sig_dict)
            self.signals_history.append(sig_dict)
            if len(self.signals_history) > 10_000:
                self.signals_history.pop(0)

            # 5. Evaluate hype score for this ticker
            hype_metrics, burst_anoms = self.hype_scorer.evaluate_step(symbol, now_ts=now_ts)
            hype_records.append(hype_metrics)
            anomalies.extend(burst_anoms)

            # 6. Check for NEAR_DUPLICATE_CAMPAIGN anomaly
            if cluster_id:
                stats = self.lsh.get_cluster_stats(cluster_id)
                if stats:
                    camp_anom = self.hype_scorer.check_near_duplicate_campaign(
                        cluster_id=cluster_id,
                        cluster_stats=stats,
                        symbol=symbol,
                        now_ts=now_ts,
                    )
                    if camp_anom:
                        anomalies.append(camp_anom)

        return signals, anomalies, hype_records

    def get_slice(
        self,
        ticker: str,
        window_start: str,
        window_end: str,
    ) -> dict[str, Any]:
        """
        Tool handler for REQUEST_SOCIAL_SLICE (ARCHITECTURE.md §4.4.2).
        """
        dt_start = datetime.datetime.fromisoformat(window_start.replace("Z", "+00:00"))
        dt_end = datetime.datetime.fromisoformat(window_end.replace("Z", "+00:00"))
        ts_start = dt_start.timestamp()
        ts_end = dt_end.timestamp()

        matched = [
            s for s in self.signals_history
            if s.get("ticker") == ticker
            and ts_start <= float(s.get("ts_numeric", 0.0)) <= ts_end
        ]

        channels = list({s.get("channel_id") for s in matched if s.get("channel_id")})
        cta_counts: dict[str, int] = collections.defaultdict(int)
        for s in matched:
            cta_counts[s.get("cta_class", "NEUTRAL")] += 1

        near_dup_clusters = list({
            s.get("near_dup_cluster_id") for s in matched
            if s.get("near_dup_cluster_id")
        })

        peak_hype = self.hype_scorer.states.get(ticker, None)
        hype_peak = peak_hype.current_hype_score if peak_hype else 0.0

        return {
            "ticker": ticker,
            "window_start": window_start,
            "window_end": window_end,
            "channels": channels,
            "message_count": len(matched),
            "hype_peak": round(hype_peak, 2),
            "cta_breakdown": dict(cta_counts),
            "near_duplicate_campaigns": near_dup_clusters,
            "first_trigger_ts": matched[0]["ts_posted"] if matched else None,
            "top_messages": [s.get("signal_id") for s in matched[:10]],
        }
