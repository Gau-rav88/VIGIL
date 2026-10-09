from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vigil_common.models.anomaly import AnomalyEvent

from .detectors import (
    Detector,
    PriceJumpDetector,
    SpoofingLayeringDetector,
    SpreadDepthDetector,
    SynchronizedOrdersDetector,
    VolumeSpikeDetector,
    WashCycleDetector,
    load_detectors_config,
)


class QuantTelemetryEngine:
    """Multi-detector engine coordinating all quantitative microstructure anomaly detectors."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_detectors_config()
        self.vol_detector = VolumeSpikeDetector(self.config)
        self.price_detector = PriceJumpDetector(self.config)
        self.spread_detector = SpreadDepthDetector(self.config)
        self.spoof_detector = SpoofingLayeringDetector(self.config)
        self.wash_detector = WashCycleDetector(self.config)
        self.sync_detector = SynchronizedOrdersDetector(self.config)

        self.detectors: list[Detector] = [
            self.vol_detector,
            self.price_detector,
            self.spread_detector,
            self.spoof_detector,
            self.wash_detector,
            self.sync_detector,
        ]
        self._trade_detectors: list[Detector] = [
            self.vol_detector,
            self.price_detector,
            self.wash_detector,
            self.spoof_detector,
        ]
        self._l2_detectors: list[Detector] = [self.spread_detector]
        self._l3_detectors: list[Detector] = [self.spoof_detector, self.sync_detector]
        self.total_processed = 0
        self.anomalies_emitted = 0

    def process_event(self, event_type: str, data: dict[str, Any]) -> list[AnomalyEvent]:
        self.total_processed += 1
        anomalies: list[AnomalyEvent] = []
        target_dets: Sequence[Detector]
        if event_type == "trade":
            target_dets = self._trade_detectors
        elif event_type == "l2":
            target_dets = self._l2_detectors
        elif event_type == "l3":
            target_dets = self._l3_detectors
        else:
            target_dets = self.detectors

        for det in target_dets:
            try:
                res = det.on_event(event_type, data)
                if res:
                    anomalies.extend(res)
            except Exception:
                # Log or isolate individual detector failures
                pass

        self.anomalies_emitted += len(anomalies)
        return anomalies

    def reload_config(self, new_config: dict[str, Any]) -> None:
        self.config = new_config
        for det in self.detectors:
            det.config = new_config
            det.config_hash = det._calc_config_hash()
