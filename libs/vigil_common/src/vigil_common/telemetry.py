from prometheus_client import Counter, Gauge, Histogram

# Ingestion metrics
INGEST_LATENCY = Histogram(
    "vigil_ingest_latency_seconds",
    "Processing latency from network receipt to normalized publish ack",
    ["stream"],
    buckets=[0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0],
)

INGEST_EVENTS_TOTAL = Counter(
    "vigil_ingest_events_total",
    "Total events processed by ingestion plane",
    ["stream", "status"],
)

INGEST_SHED_TOTAL = Counter(
    "vigil_ingest_shed_total",
    "Total events shed due to backpressure / high watermark",
    ["kind"],
)

# Anomaly detection metrics
DETECT_LATENCY = Histogram(
    "vigil_detect_latency_seconds",
    "Latency from event time to anomaly emission",
    ["agent", "type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

ANOMALIES_EMITTED_TOTAL = Counter(
    "vigil_anomalies_emitted_total",
    "Count of anomalies emitted by type and severity",
    ["agent", "type", "severity"],
)

# Case lifecycle metrics
CASE_DURATION = Histogram(
    "vigil_case_duration_seconds",
    "Time taken from case trigger to draft dossier",
    ["symbol"],
    buckets=[30, 60, 120, 180, 240, 300, 600],
)

ACTIVE_CASES = Gauge(
    "vigil_active_cases",
    "Number of active cases by stage",
    ["stage"],
)
