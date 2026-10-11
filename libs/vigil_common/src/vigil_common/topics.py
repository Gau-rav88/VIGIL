from __future__ import annotations


class Topics:
    MARKET_TRADES_RAW = "market.trades.raw"
    MARKET_L2_RAW = "market.l2.raw"
    MARKET_L3_RAW = "market.l3.raw"
    MARKET_TRADES_NORM = "market.trades.norm"
    MARKET_L2_NORM = "market.l2.norm"
    MARKET_L3_NORM = "market.l3.norm"
    SOCIAL_MESSAGES_RAW = "social.messages.raw"
    SOCIAL_SIGNALS_NORM = "social.signals.norm"
    HYPE_SCORES_NORM = "hype.scores.norm"
    ANOMALY_MARKET = "anomaly.market"
    ANOMALY_SOCIAL = "anomaly.social"
    ANOMALY_FUSED = "anomaly.fused"
    GRAPH_UPDATES = "graph.updates"
    CASE_TRIGGER = "case.trigger"
    CASE_EVENTS = "case.events"
    HEALTH_EVENTS = "health.events"
    DLQ_MARKET = "dlq.market"
    DLQ_SOCIAL = "dlq.social"
    DLQ_SINK = "dlq.sink"

    @classmethod
    def all_topics(cls) -> list[str]:
        return [
            v for k, v in vars(cls).items()
            if isinstance(v, str) and not k.startswith("_") and k != "all_topics"
        ]
