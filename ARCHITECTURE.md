# ARCHITECTURE — Project VIGIL
### Implementation Specification for Automated Code Scaffolding

| Field | Value |
|---|---|
| Document version | 1.0.0 |
| Companion | `PRD.md` (requirements, schemas §5, acceptance criteria §6) |
| Language/runtime | Python 3.12 (backend), TypeScript 5 / Node 20 (frontend) |
| Repo layout | Monorepo, `uv` workspace (Python), `pnpm` (frontend) |

> **Instructions to the code generator.** (1) Generate files exactly at the paths in §10. (2) Treat names of topics, tables, env vars, endpoints, and JSON fields in this document as normative. (3) Where a formula or threshold is given, implement it literally and read parameters from `config/*.yaml`. (4) Implement in the order given in §14. (5) Never hard-code secrets. (6) Every service MUST expose `GET /healthz` (liveness), `GET /readyz` (readiness) and `GET /metrics` (Prometheus) on port `8000` unless stated otherwise (workers run a tiny `uvicorn` health app on `HEALTH_PORT`).

---

## 1. System Topology

```mermaid
flowchart LR
  subgraph SRC["External / Simulated Sources"]
    EXF["Exchange / Regulator privileged feed<br/>(L2/L3 + trades)"]
    SIM["VIGIL Simulator<br/>ws://simulator:8090/ws/market<br/>ws://simulator:8090/ws/social"]
    TG["Telegram public channels"]
    DC["Discord / Reddit / X / StockTwits / Forums"]
  end

  subgraph ING["Ingestion Plane"]
    MI["market_ingest<br/>(validate, dedupe, stamp)"]
    SI["social_ingest<br/>(adapters, visibility gate)"]
  end

  subgraph BUS["Streaming Backbone (Redpanda / Kafka API)"]
    KR["market.*.raw · social.messages.raw"]
    KN["market.*.norm"]
    KS["social.signals.norm"]
    KA["anomaly.market · anomaly.social · anomaly.fused"]
    KG["graph.updates"]
    KC["case.trigger · case.events"]
    DLQ["dlq.market · dlq.social"]
  end

  subgraph AG["Agentic Plane"]
    QTA["Quant Telemetry Agent"]
    SIA["Social Intelligence Agent<br/>(parser + hype scorer)"]
    ALN["Alignment Engine"]
    CAA["Cyber-Forensics Attribution Agent"]
    ORC["Orchestrator Agent<br/>(LangGraph)"]
    RBUS["Redis Streams<br/>bus:agent:commands / bus:agent:results"]
  end

  subgraph STO["Storage Plane"]
    SINK["stream_sink<br/>(batch writers + raw archiver)"]
    TS[("TimescaleDB<br/>ticks · bars · hype · anomalies · cases · ledger")]
    NEO[("Neo4j<br/>entity graph")]
    RED[("Redis<br/>hot state, dedupe, bus")]
    S3[("MinIO / S3<br/>raw archive · evidence · dossiers")]
  end

  subgraph EVD["Evidence Generation Engine"]
    EE["evidence_engine<br/>capture · merkle · ledger · sign · PDF"]
    VER["verifier (API + CLI)"]
  end

  subgraph API["Serving Plane"]
    GW["api (FastAPI)<br/>REST + WebSocket"]
    FE["frontend (Next.js)"]
  end

  EXF --> MI
  SIM --> MI
  SIM --> SI
  TG --> SI
  DC --> SI
  MI --> KR --> MI
  MI --> KN
  MI --> DLQ
  SI --> KR
  SI --> DLQ
  KN --> QTA
  KN --> SINK
  KR --> SINK
  KR --> SIA
  SIA --> KS
  KS --> SINK
  KS --> CAA
  QTA --> KA
  SIA --> KA
  KA --> ALN
  ALN --> KA
  ALN --> KC
  KN --> CAA
  CAA --> KG
  KG --> NEO
  KC --> ORC
  ORC <--> RBUS
  RBUS <--> QTA
  RBUS <--> SIA
  RBUS <--> CAA
  CAA <--> NEO
  SINK --> TS
  SINK --> S3
  QTA <--> RED
  SIA <--> RED
  ORC --> EE
  EE --> TS
  EE --> S3
  EE --> VER
  GW --> TS
  GW --> NEO
  GW --> S3
  GW --> ORC
  GW --> EE
  GW --> VER
  KA --> GW
  KC --> GW
  GW <--> FE
```

**Data-flow summary**
1. Feeds → `market_ingest` / `social_ingest` → raw topics (byte-exact) and normalized topics (validated + stamped).
2. `stream_sink` persists every normalized event to TimescaleDB (batch `COPY`) and archives raw bytes to MinIO.
3. Agents consume normalized topics and emit `anomaly.*` events; the Alignment Engine fuses them into `CROSS_MODAL_ALIGNMENT`, which publishes `case.trigger`.
4. The Orchestrator drives a case through the state machine (§5), calling agents via Redis Streams "tool" requests, then invokes the Evidence Engine.
5. The API serves the UI and exposes verification.

---

## 2. Technology Stack & Rationale

| Concern | Selection | Version (pin) | Rationale |
|---|---|---|---|
| Streaming backbone | **Redpanda** (Kafka API) | v24.2.x | Single binary, Kafka-compatible, trivial in Docker Compose, low latency; swap to Apache Kafka in prod with no code change (use `aiokafka`). |
| Hot state / agent RPC | **Redis 7.4** (Streams, Hashes, `SETNX`) | 7.4 | Consumer-group streams for typed agent requests; sub-ms dedupe & warm-state snapshots. |
| Time-series / relational | **TimescaleDB** (PostgreSQL 16) | latest-pg16 | Hypertables + continuous aggregates + compression; SQL for evidence queries; same engine hosts cases, ledger, LangGraph checkpoints → fewer moving parts than ClickHouse for MVP. ClickHouse remains the documented scale-out path for tick storage (§3.5). |
| Graph DB | **Neo4j 5 Community** + APOC (+ GDS optional) | 5.24 | Native Cypher cycle/path queries, mature Cytoscape-friendly export. In-process clustering uses **NetworkX** (Louvain, seeded) for determinism; GDS is an optional accelerator for > 50k nodes. |
| Object store | **MinIO** (S3 API) | latest | Raw archive, evidence slices, dossiers; supports Object Lock (WORM) in prod. |
| Agent orchestration | **LangGraph** (+ `langgraph-checkpoint-postgres`) | ≥ 0.2 | Explicit state-machine graphs, durable checkpoints, conditional edges, human-in-the-loop `interrupt`. Chosen over AutoGen/CrewAI because the workflow must be **deterministic, resumable, and auditable**; free-form multi-agent chat is not acceptable for evidentiary systems. |
| LLM | **Anthropic Claude API** via `anthropic` SDK; model from env `LLM_MODEL` (default `claude-sonnet-5-5`) | — | Used only for semantic classification of ambiguous messages and narrative drafting with schema-constrained output (§4.4). Always has deterministic fallback. |
| Embeddings (fallback classifier, near-dup) | `sentence-transformers` `intfloat/multilingual-e5-small` | — | Multilingual incl. Hinglish; CPU-friendly. |
| Backend API | **FastAPI** + `uvicorn` (uvloop) + Pydantic v2 | FastAPI ≥ 0.115 | Async, OpenAPI 3.1, WebSockets. |
| Async processing | **Python AsyncIO** (`aiokafka`, `asyncpg`, `redis.asyncio`, `neo4j` async driver, `orjson`) | — | Single-threaded per partition, high throughput without Celery overhead. CPU-heavy tasks (xcorr permutation tests, PDF render, Louvain) run in `ProcessPoolExecutor`. **Celery/Ray are intentionally not used in MVP**; Ray is the documented scale-out option for the Alignment Engine. |
| Numerics | `numpy`, `scipy`, `pandas` (batch only), `numba` (hot loops optional) | — | Detectors. |
| Crypto | `cryptography` (Ed25519), `hashlib` (SHA-256), `rfc8785` (JCS) | — | Standard, audited primitives. |
| PDF | **WeasyPrint** + Jinja2 + `matplotlib` + `qrcode` | — | HTML→PDF deterministic layout; charts hashed as evidence. |
| Frontend | **Next.js 14 (App Router)**, TypeScript, **Tailwind CSS**, **Recharts**, **Cytoscape.js** (+ `cytoscape-fcose`), TanStack Query, Zustand | — | Required stack; Cytoscape handles 500+ node graphs with compound/cluster styling. |
| Observability | OpenTelemetry → OTel Collector → Prometheus/Grafana; `structlog` JSON logs | — | Trace propagation via Kafka headers `traceparent`. |
| Auth | OIDC JWT (RS256 prod; HS256 dev issuer endpoint `/api/v1/auth/dev-token`) | — | RBAC per PRD FR-API-02. |
| Tooling | `uv`, `ruff`, `mypy --strict`, `pytest`, `pytest-asyncio`, `testcontainers`, Playwright, `locust` (load) | — | CI quality gates. |

---

## 3. Data Plane

### 3.1 Kafka topics (create via `infra/redpanda/create_topics.sh`)

| Topic | Key | Partitions | Retention | Value | Producer → Consumers |
|---|---|---|---|---|---|
| `market.trades.raw` | `symbol` | 16 | 24 h | raw bytes (JSON) | market_ingest → stream_sink(archiver) |
| `market.l2.raw` | `symbol` | 16 | 6 h | raw bytes | same |
| `market.l3.raw` | `symbol` | 16 | 6 h | raw bytes | same |
| `market.trades.norm` | `symbol` | 16 | 48 h | `TradeTick` JSON | market_ingest → quant_telemetry, attribution, stream_sink |
| `market.l2.norm` | `symbol` | 16 | 12 h | `L2Snapshot` | → quant_telemetry, stream_sink |
| `market.l3.norm` | `symbol` | 16 | 12 h | `L3OrderEvent` | → quant_telemetry, attribution, stream_sink |
| `social.messages.raw` | `channel_id` | 8 | 7 d | `SocialMessage` | social_ingest → social_intel, stream_sink |
| `social.signals.norm` | `ticker` | 8 | 7 d | `SocialSignal` | social_intel → hype_scorer, attribution, stream_sink |
| `anomaly.market` | `symbol` | 8 | 7 d | `AnomalyEvent` | quant_telemetry → alignment, api, stream_sink |
| `anomaly.social` | `symbol` | 8 | 7 d | `AnomalyEvent` | social_intel → alignment, api, stream_sink |
| `anomaly.fused` | `symbol` | 8 | 30 d | `AnomalyEvent` | alignment/attribution → orchestrator, api, stream_sink |
| `graph.updates` | `account_id` | 8 | 7 d | `GraphUpdate` (JSON) | attribution(loader) → attribution(writer) |
| `case.trigger` | `symbol` | 4 | 30 d | `CaseTrigger` | alignment → orchestrator |
| `case.events` | `case_id` | 4 | 90 d | `CaseEvent` | orchestrator → api (WS fan-out), stream_sink |
| `health.events` | `service` | 1 | 7 d | `HealthEvent` | all → api |
| `dlq.market`, `dlq.social` | — | 2 | 14 d | `{original_b64, error, stage, ts}` | ingest → ops |

Producer settings: `acks=all` (prod) / `acks=1` (dev via `KAFKA_ACKS`), `linger_ms=5`, `compression_type=zstd`, `enable_idempotence=true`. Consumer settings: manual commit after successful batch handling, `max_poll_records=2000`.
Headers on every message: `traceparent`, `schema_version`, `producer`.

### 3.2 Redis keyspace

| Key / stream | Type | Purpose | TTL |
|---|---|---|---|
| `dedupe:{stream}:{event_id}` | string (`SET NX EX`) | idempotency | 600 s |
| `state:qta:{symbol}` | hash (msgpack blob) | warm-restart snapshot of rolling stats | 1 h |
| `state:hype:{ticker}` | hash | hype window state | 1 h |
| `bus:agent:commands` | stream (group `agents`) | orchestrator → agents `AgentMessage` | maxlen 100k |
| `bus:agent:results` | stream (group `orchestrator`) | agents → orchestrator | maxlen 100k |
| `watchlist:symbols` | zset (score = risk) | symbols for which graph edges are materialized | — |
| `ratelimit:{role}:{route}` | string | API limiter | 60 s |
| `mrs:{symbol}` | string (json) | latest MRS for live heatmap | 120 s |

### 3.3 TimescaleDB schema (Alembic migration `0001_core_tables.py`; raw SQL below is normative)

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS vigil;
SET search_path TO vigil, public;

-- ===== market =====
CREATE TABLE trades (
  ts              timestamptz NOT NULL,           -- ts_exchange
  event_id        uuid        NOT NULL,
  exchange        text        NOT NULL,
  symbol          text        NOT NULL,
  trade_id        text        NOT NULL,
  seq             bigint      NOT NULL,
  price           numeric(18,8) NOT NULL,
  qty             bigint      NOT NULL,
  aggressor_side  text        NOT NULL,
  buyer_account   text        NOT NULL,
  seller_account  text        NOT NULL,
  buyer_broker    text        NOT NULL,
  seller_broker   text        NOT NULL,
  buyer_gateway   text, seller_gateway text,
  buy_order_id    text, sell_order_id text,
  buyer_device    text, seller_device text,
  buyer_ip        text, seller_ip text,
  buyer_asn       integer, seller_asn integer,
  buyer_api_client text, seller_api_client text,
  buyer_latency_us integer, seller_latency_us integer,
  market_segment  text, is_synthetic boolean NOT NULL DEFAULT false,
  ts_ingest       timestamptz NOT NULL,
  PRIMARY KEY (symbol, trade_id, ts)
);
SELECT create_hypertable('trades','ts', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX trades_buyer_idx  ON trades (buyer_account,  ts DESC);
CREATE INDEX trades_seller_idx ON trades (seller_account, ts DESC);
ALTER TABLE trades SET (timescaledb.compress, timescaledb.compress_segmentby='symbol', timescaledb.compress_orderby='ts DESC');
SELECT add_compression_policy('trades', INTERVAL '3 days');

CREATE TABLE orders_l3 (
  ts timestamptz NOT NULL, event_id uuid NOT NULL, exchange text NOT NULL, symbol text NOT NULL, seq bigint NOT NULL,
  order_id text NOT NULL, orig_order_id text, action text NOT NULL, side text NOT NULL, order_type text,
  price numeric(18,8), qty bigint, leaves_qty bigint, account_id text NOT NULL, broker_id text NOT NULL,
  gateway_id text, device_fp text, ip_hash text, asn integer, api_client_id text, order_to_ack_us integer,
  is_synthetic boolean NOT NULL DEFAULT false, ts_ingest timestamptz NOT NULL,
  PRIMARY KEY (symbol, seq, ts)
);
SELECT create_hypertable('orders_l3','ts', chunk_time_interval => INTERVAL '6 hours');
CREATE INDEX orders_l3_acct_idx ON orders_l3 (account_id, ts DESC);

CREATE TABLE l2_snapshots (
  ts timestamptz NOT NULL, symbol text NOT NULL, seq bigint NOT NULL, exchange text NOT NULL,
  bids jsonb NOT NULL, asks jsonb NOT NULL, depth_levels int NOT NULL, is_synthetic boolean NOT NULL DEFAULT false,
  PRIMARY KEY (symbol, seq, ts)
);
SELECT create_hypertable('l2_snapshots','ts', chunk_time_interval => INTERVAL '6 hours');

CREATE TABLE l2_metrics_1s (            -- derived by quant_telemetry via sink
  ts timestamptz NOT NULL, symbol text NOT NULL,
  best_bid numeric(18,8), best_ask numeric(18,8), rel_spread double precision,
  bid_depth_5 bigint, ask_depth_5 bigint, depth_imbalance double precision,
  PRIMARY KEY (symbol, ts)
);
SELECT create_hypertable('l2_metrics_1s','ts', chunk_time_interval => INTERVAL '1 day');

CREATE MATERIALIZED VIEW bars_1s WITH (timescaledb.continuous) AS
SELECT time_bucket('1 second', ts) AS ts, symbol,
       first(price, ts) AS open, max(price) AS high, min(price) AS low, last(price, ts) AS close,
       sum(qty) AS volume, count(*) AS n_trades
FROM trades GROUP BY 1,2 WITH NO DATA;
SELECT add_continuous_aggregate_policy('bars_1s', start_offset => INTERVAL '2 hours', end_offset => INTERVAL '1 second', schedule_interval => INTERVAL '5 seconds');

-- ===== social =====
CREATE TABLE social_messages (
  ts timestamptz NOT NULL, event_id uuid NOT NULL, platform text NOT NULL, channel_id text NOT NULL, channel_name text,
  channel_visibility text NOT NULL, message_id text NOT NULL, author_id text NOT NULL, text text NOT NULL, lang text,
  reply_to_message_id text, forwarded_from_channel_id text, views int, reactions int, urls text[], raw_sha256 text NOT NULL,
  is_synthetic boolean NOT NULL DEFAULT false, ts_ingest timestamptz NOT NULL,
  PRIMARY KEY (platform, channel_id, message_id, ts)
);
SELECT create_hypertable('social_messages','ts', chunk_time_interval => INTERVAL '1 day');

CREATE TABLE social_signals (
  ts timestamptz NOT NULL, signal_id uuid NOT NULL, message_event_id uuid NOT NULL, platform text NOT NULL, channel_id text NOT NULL,
  author_id text NOT NULL, ticker text NOT NULL, ticker_confidence real NOT NULL, mention_type text, cta_class text NOT NULL,
  cta_confidence real, target_price numeric(18,8), scheduled_action_time timestamptz, urgency real, sentiment real,
  near_dup_cluster_id text, forward_cascade_depth int DEFAULT 0, raw_sha256 text NOT NULL, parser_mode text NOT NULL, parser_version text,
  PRIMARY KEY (signal_id, ts)
);
SELECT create_hypertable('social_signals','ts', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX social_signals_ticker_idx ON social_signals (ticker, ts DESC);

CREATE TABLE hype_scores (
  ts timestamptz NOT NULL, ticker text NOT NULL, hype_score real NOT NULL,
  f_rate real, f_auth real, f_cta real, f_dup real, f_urg real, f_xch real,
  msg_count int, unique_authors int, channels int,
  PRIMARY KEY (ticker, ts)
);
SELECT create_hypertable('hype_scores','ts', chunk_time_interval => INTERVAL '1 day');

-- ===== analytics outputs =====
CREATE TABLE anomalies (
  detected_at timestamptz NOT NULL, anomaly_id uuid NOT NULL, type text NOT NULL, source_agent text NOT NULL, symbol text NOT NULL,
  window_start timestamptz NOT NULL, window_end timestamptz NOT NULL, score real NOT NULL, severity text NOT NULL,
  metrics jsonb NOT NULL, participants text[], evidence_refs jsonb NOT NULL, detector_version text NOT NULL, config_hash text NOT NULL,
  case_id uuid, PRIMARY KEY (anomaly_id, detected_at)
);
SELECT create_hypertable('anomalies','detected_at', chunk_time_interval => INTERVAL '7 days');
CREATE INDEX anomalies_symbol_idx ON anomalies (symbol, window_start DESC);

CREATE TABLE mrs_1m (
  ts timestamptz NOT NULL, symbol text NOT NULL, mrs real NOT NULL, components jsonb NOT NULL, PRIMARY KEY (symbol, ts)
);
SELECT create_hypertable('mrs_1m','ts', chunk_time_interval => INTERVAL '1 day');

-- ===== cases, ledger, dossiers =====
CREATE TYPE case_status AS ENUM ('OPENED','ENRICHING','ALIGNED','ATTRIBUTING','ASSESSING','DRAFTING','VALIDATING','SIGNING',
  'PENDING_REVIEW','APPROVED','PUBLISHED','REJECTED','REWORK','WATCHLIST','CLOSED_NO_ACTION','FAILED');

CREATE TABLE cases (
  case_id uuid PRIMARY KEY, symbol text NOT NULL, exchange text NOT NULL, status case_status NOT NULL,
  window_start timestamptz NOT NULL, window_end timestamptz NOT NULL, trigger_anomaly_id uuid NOT NULL,
  mrs real, overall_confidence real, completeness real, assigned_to text, state jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  is_synthetic boolean NOT NULL DEFAULT false
);
CREATE INDEX cases_status_idx ON cases (status, updated_at DESC);

CREATE TABLE case_events (
  id bigserial PRIMARY KEY, case_id uuid NOT NULL REFERENCES cases, ts timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL, kind text NOT NULL, payload jsonb NOT NULL
);

CREATE TABLE evidence_objects (
  evidence_id text PRIMARY KEY, case_id uuid NOT NULL REFERENCES cases, type text NOT NULL, sha256 char(64) NOT NULL,
  uri text NOT NULL, bytes bigint NOT NULL, captured_at timestamptz NOT NULL, meta jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE evidence_ledger (
  entry_id bigserial PRIMARY KEY, ts timestamptz NOT NULL DEFAULT now(), case_id uuid,
  entry_type text NOT NULL,                  -- EVIDENCE|DOSSIER|HUMAN_ACTION|AGENT_DECISION|LLM_CALL|ANCHOR|KEY_EVENT
  actor text NOT NULL, subject_sha256 char(64) NOT NULL, payload jsonb NOT NULL DEFAULT '{}',
  prev_entry_hash char(64) NOT NULL, entry_hash char(64) NOT NULL UNIQUE
);
-- entry_hash = hex(SHA256( prev_entry_hash || '|' || subject_sha256 || '|' || to_char(ts at utc,'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') || '|' || entry_type || '|' || actor ))
-- Genesis prev_entry_hash = 64 zeros.
CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'evidence_ledger is append-only'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER ledger_no_update BEFORE UPDATE OR DELETE ON evidence_ledger FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER ledger_no_truncate BEFORE TRUNCATE ON evidence_ledger FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();

CREATE TABLE dossiers (
  dossier_id uuid PRIMARY KEY, case_id uuid NOT NULL REFERENCES cases, version int NOT NULL, supersedes uuid,
  json_uri text NOT NULL, pdf_uri text, sig_uri text, bundle_uri text, digest_sha256 char(64) NOT NULL,
  merkle_root char(64) NOT NULL, key_id text NOT NULL, narrative_mode text NOT NULL,   -- LLM|TEMPLATE
  review_status text NOT NULL DEFAULT 'NOT_REVIEWED', created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, version)
);
CREATE TABLE signing_keys (
  key_id text PRIMARY KEY, alg text NOT NULL DEFAULT 'Ed25519', public_key_pem text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), retired_at timestamptz
);
CREATE TABLE audit_log (
  id bigserial PRIMARY KEY, ts timestamptz NOT NULL DEFAULT now(), user_id text, role text, method text, path text,
  status int, request_hash char(64), meta jsonb
);
CREATE TABLE link_feedback (
  id bigserial PRIMARY KEY, case_id uuid NOT NULL, user_id text NOT NULL, a_account text NOT NULL, b_account text NOT NULL,
  verdict text NOT NULL CHECK (verdict IN ('CONFIRM','REJECT')), comment text, ts timestamptz NOT NULL DEFAULT now()
);
```
LangGraph checkpoint tables are created by `PostgresSaver.setup()` in schema `vigil_lg` at orchestrator startup.

### 3.4 Object-store layout (MinIO buckets)
```
vigil-raw/       market/{trades|l2|l3}/YYYY/MM/DD/HH/part-{partition}-{start_offset}.ndjson.zst
                 social/YYYY/MM/DD/HH/part-{partition}-{start_offset}.ndjson.zst
vigil-evidence/  {case_id}/{evidence_id}.{ndjson.zst|json|png}
vigil-dossiers/  {case_id}/v{version}/dossier.json | dossier.pdf | dossier.sig | bundle.zip
vigil-anchors/   daily/YYYY-MM-DD.json   (Merkle root of ledger entries for that day; Object Lock in prod)
```

### 3.5 Scale-out notes (documented, not implemented in MVP)
- Tick storage can move to ClickHouse (`ReplacingMergeTree` ordered by `(symbol, ts, trade_id)`); `stream_sink` has a `TickSink` interface with `TimescaleTickSink` (MVP) and `ClickHouseTickSink` (stub).
- Alignment permutation tests can be offloaded to Ray (`AlignmentExecutor` interface: `ProcessPoolExecutor` default, `RayExecutor` stub).

---

## 4. Service Responsibilities & Internal Interfaces

### 4.1 `market_ingest`
- Entry: `python -m market_ingest.main`; env `MARKET_ADAPTER` ∈ {`websocket`,`file_replay`}; `MARKET_WS_URL` (default `ws://simulator:8090/ws/market`).
- Pipeline per message: `recv → t_recv=time_ns() → publish raw bytes to market.<kind>.raw (fire-and-forget batched) → orjson.loads → fastjsonschema validate (pre-compiled validators keyed by event kind) → dedupe (in-process LRU 1M + Redis NX) → seq-gap check → stamp ts_received, ts_ingest, ingest_latency_us → publish to market.<kind>.norm → observe Histogram`.
- `ingest_latency_us = (time_ns_at_norm_publish_ack − t_recv) / 1000`. Histogram buckets (s): `[.001,.002,.005,.01,.025,.05,.1,.15,.2,.3,.5,1]`.
- Overload policy: if consumer-side lag or local queue > `INGEST_QUEUE_HIGH_WATERMARK` (50k), drop `l2` deltas only; count `vigil_ingest_shed_total{kind="l2"}`.
- Interface:
```python
class MarketFeedAdapter(Protocol):
    async def stream(self) -> AsyncIterator[tuple[str, bytes]]: ...   # (kind, raw_bytes), kind in {"trade","l2","l3"}
```

### 4.2 `social_ingest`
- Adapters: `SyntheticWsAdapter` (default, `ws://simulator:8090/ws/social`), `TelegramPublicChannelAdapter` (Telethon; requires `TELEGRAM_API_ID/HASH/SESSION`; channel list from `config/social_channels.yaml`; public channels only), `FileReplayAdapter`.
- Steps: pseudonymize `author_id = b64url(HMAC_SHA256(PSEUDONYM_PEPPER, "handle|"+platform+"|"+raw_author)[:16])`, compute `raw_sha256 = sha256(canonical raw JSON bytes)`, enforce `channel_visibility ∈ {public,lawful_access}`, validate against `social_message` schema, publish to `social.messages.raw`. Violations → `dlq.social`.

### 4.3 `stream_sink`
Consumer groups `sink-timescale-*` and `sink-archive-*`.
- `TimescaleTickSink`: batch (≤ 2000 rows or 200 ms) → `asyncpg.copy_records_to_table` into a temp table → `INSERT … ON CONFLICT DO NOTHING` into the hypertable. Offsets committed after successful insert.
- Also persists: `social_messages`, `social_signals`, `hype_scores`, `anomalies`, `mrs_1m`, `l2_metrics_1s`, `case_events`.
- `RawArchiver`: rolls files hourly or at 64 MB (whichever first), zstd-compressed NDJSON, computes SHA-256 per file, uploads, and appends a ledger entry (`entry_type='EVIDENCE'`, payload `{uri, topic, partition, offset_start, offset_end}`).

### 4.4 Agents (all in `services/agents/*`; each is a long-running consumer **and** a Redis-Streams tool server)

**Common `AgentMessage` envelope** (Pydantic, `libs/vigil_common/models/agent_messages.py`):
```python
class AgentMessage(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    msg_id: UUID
    correlation_id: UUID            # = request msg_id for results
    case_id: UUID | None
    sender: Literal["orchestrator","quant_telemetry","social_intel","attribution","alignment","evidence_engine","api"]
    recipient: str
    type: Literal[
      "REQUEST_MARKET_SLICE","MARKET_SLICE_RESULT",
      "REQUEST_SOCIAL_SLICE","SOCIAL_SLICE_RESULT",
      "REQUEST_ALIGNMENT","ALIGNMENT_RESULT",
      "REQUEST_ATTRIBUTION","ATTRIBUTION_RESULT",
      "DIRECTIVE","ERROR"]
    payload: dict[str, Any]
    ts: datetime
    ttl_s: int = 120
    attempt: int = 1
    idempotency_key: str            # sha256(case_id|type|canonical(payload))
```
Servers read `bus:agent:commands` via `XREADGROUP` (group `agents`, consumer = service name), filter by `recipient`, and answer on `bus:agent:results`. Orchestrator awaits by `correlation_id` with timeout.

#### 4.4.1 Quant Telemetry Agent (QTA) — `services/agents/quant_telemetry`
- Consumes `market.trades.norm`, `market.l2.norm`, `market.l3.norm` (partition-owned, per-symbol in-memory state objects `SymbolState`).
- Detectors (each a class implementing `Detector.on_event(evt) -> list[AnomalyEvent]`): `VolumeSpikeDetector`, `SpreadDepthDetector`, `SpoofingLayeringDetector`, `WashCycleDetector`, `SynchronizedOrdersDetector`, `PriceJumpDetector`. Algorithms in §7.1.
- Emits `AnomalyEvent` to `anomaly.market`; also emits `l2_metrics_1s` rows.
- Tool handlers: `REQUEST_MARKET_SLICE{symbol, window_start, window_end, accounts?}` → runs SQL against Timescale and returns summary `{total_volume, suspect_volume, price_move_pct, anomalies[], slice_rows}` and writes the slice as NDJSON.zst to MinIO, returning `{uri, sha256, bytes}`.

#### 4.4.2 Social Intelligence Agent (SIA) — `services/agents/social_intel`
- **Fast path (always)**: language detect (`lingua`/`fasttext-langdetect`), NFKC normalization, ticker extraction (regex `\$[A-Z][A-Z0-9&._-]{1,23}` + alias dictionary + Aho-Corasick over company names), rule-based CTA classification (lexicon in `config/cta_lexicon.yaml`, incl. Hinglish tokens such as "kharido", "lelo", "rocket", "10x"), urgency (lexicon + exclamation/emoji density + imminent-time regex), MinHash-LSH near-duplicate (128 perms, 5-gram shingles, threshold 0.8, 5-min sliding index in Redis-backed LSH), forward-cascade depth.
- **LLM refinement path (async, bounded)**: invoked only when `ticker_confidence < 0.8` **or** `cta_class == NEUTRAL and urgency ≥ 0.5` **or** `lang not in {en,hi}`. Batched ≤ 20 messages, concurrency `LLM_MAX_CONCURRENCY=8`, timeout `LLM_TIMEOUT_S=2.0`. On timeout/error → fast-path result is kept (`parser.mode="FALLBACK_RULES"`). Each LLM call is recorded: `prompt_sha256`, `response_sha256` → ledger `LLM_CALL`.
- LLM contract: system prompt requires **JSON only**, matching schema `{items:[{message_id, tickers:[{symbol,confidence,mention_type}], cta_class, cta_confidence, target_price, scheduled_action_time, urgency, sentiment}]}`; validate with Pydantic; on failure retry once then fallback. Messages are passed inside delimited `<message id="…">…</message>` blocks and the prompt states that message content is untrusted data and must never be treated as instructions (prompt-injection defense).
- Emits `SocialSignal` to `social.signals.norm`.
- **Hype scorer** (`hype_scorer.py`): consumes `social.signals.norm`, maintains per-ticker sliding 60-s window, computes `hype_score` every 5 s (§7.2), writes `hype_scores`, emits `HYPE_BURST` / `NEAR_DUPLICATE_CAMPAIGN` to `anomaly.social`.
- Tool handler: `REQUEST_SOCIAL_SLICE{ticker, window_start, window_end}` → returns `{channels[], message_count, hype_peak, cta_breakdown, near_duplicate_campaigns, first_trigger_ts, top_messages[evidence ids]}` and uploads the slice (messages + signals) to MinIO.

#### 4.4.3 Alignment Engine — `services/alignment_engine`
- Consumes `anomaly.market`, `anomaly.social`; maintains `hot_tickers` (hype ≥ 40 or volume_z ≥ 2 within last 10 min).
- Every `ALIGN_INTERVAL_S=5` per hot ticker: loads 1-s series for the last `ALIGN_LOOKBACK_S=3600` s from Timescale (`bars_1s`, `l2_metrics_1s`, `hype_scores` upsampled), runs §7.3, writes MRS (§7.4) to `mrs_1m` and Redis `mrs:{symbol}`.
- Emits `CROSS_MODAL_ALIGNMENT` to `anomaly.fused` and a `CaseTrigger` to `case.trigger` when criteria in PRD FR-ALN-03 hold and no open case overlaps (check `cases` table).

#### 4.4.4 Cyber-Forensics Attribution Agent (CAA) — `services/agents/attribution`
- **Graph loader** (continuous): consumes `market.trades.norm`, `market.l3.norm`, `social.signals.norm`; only for symbols in `watchlist:symbols` (added when hype ≥ 40 or any anomaly; removed after 60 min of quiet) it batches `GraphUpdate` messages to `graph.updates`; the **graph writer** applies them to Neo4j in transactions of ≤ 1000 ops using `UNWIND … MERGE`. Trade edges are aggregated per `(seller, buyer, ticker, 10-s bucket)`.
- **Case attribution run** (`REQUEST_ATTRIBUTION{case_id, symbol, window_start, window_end, params}`):
  1. Candidate account set = participants of QTA anomalies in window ∪ top-N accounts by volume share ∪ accounts reacting to CTAs.
  2. Materialize evidence links (§7.5): `SHARES_FINGERPRINT`, `SYNCHRONIZED_WITH`, `REACTED_TO`, circular cycles (Cypher §6.4), broker-pathway concentration, latency-signature similarity (KS test).
  3. Build case-scoped `LINKED` edges with `weight`, `confidence`, `methods[]`.
  4. Cluster: connected components over edges with `confidence ≥ 0.60`; any component > 40 nodes is refined with NetworkX Louvain (`seed=42`, `resolution=1.0`).
  5. Create/Update `Entity` nodes (`CONTROLLED_BY` edges) with `ring_score`.
  6. Return `{rings[], leads[], metrics, graph_export_uri, sha256}`.
- Tool handler also supports `DIRECTIVE{EXCLUDE_ACCOUNT, WIDEN_WINDOW}` and `link_feedback` recomputation.

#### 4.4.5 Orchestrator Agent — see §5.

### 4.5 `evidence_engine` — see §9.
### 4.6 `api` — see §8.

---

## 5. Multi-Agent State Machine Specification

### 5.1 Roles

| Agent | Role | Trigger | Inputs | Outputs | Autonomy |
|---|---|---|---|---|---|
| Market Ingestion | Validate/stamp market data | WS message | raw feed | `market.*.norm`, DLQ | fully automatic |
| Social Ingestion | Acquire/pseudonymize public social data | adapter message | raw feed | `social.messages.raw`, DLQ | fully automatic |
| QTA | Statistical microstructure anomalies | norm market events | trades/L2/L3 | `anomaly.market` | automatic |
| SIA | Semantic parsing, hype scoring | raw social messages | messages | `social.signals.norm`, `anomaly.social` | automatic (LLM optional) |
| Alignment Engine | Cross-modal fusion, MRS | anomaly streams, timer | anomaly + series | `anomaly.fused`, `case.trigger`, `mrs_1m` | automatic |
| CAA | Graph build, attribution, ring detection | per-case request + continuous loader | trades, orders, signals | graph, `ATTRIBUTION_RESULT` | automatic; investigator can steer |
| Orchestrator | Case lifecycle, evidence compile | `case.trigger`, API directives | all results | dossier, case state | automatic until `PENDING_REVIEW`; **human gate afterwards** |
| Evidence Engine | Hash, ledger, sign, render | orchestrator call | case data | signed dossier bundle | automatic |

### 5.2 Case state schema (`libs/vigil_common/models/case.py`)

```python
class CaseStage(str, Enum):
    OPENED="OPENED"; ENRICHING="ENRICHING"; ALIGNED="ALIGNED"; ATTRIBUTING="ATTRIBUTING"
    ASSESSING="ASSESSING"; DRAFTING="DRAFTING"; VALIDATING="VALIDATING"; SIGNING="SIGNING"
    PENDING_REVIEW="PENDING_REVIEW"; APPROVED="APPROVED"; PUBLISHED="PUBLISHED"
    REJECTED="REJECTED"; REWORK="REWORK"; WATCHLIST="WATCHLIST"
    CLOSED_NO_ACTION="CLOSED_NO_ACTION"; FAILED="FAILED"

class WindowParams(BaseModel):
    start: datetime; end: datetime
    widen_count: int = 0                      # max 2

class CaseState(TypedDict, total=False):      # LangGraph state
    case_id: str
    symbol: str; exchange: str
    stage: CaseStage
    trigger_anomaly_id: str
    window: WindowParams
    market_slice: dict | None                 # MARKET_SLICE_RESULT.payload
    social_slice: dict | None
    alignment: dict | None                    # best_lag_s, xcorr_peak, p_value
    attribution: dict | None                  # rings, leads, metrics, graph_export_uri
    anomalies: list[str]                      # anomaly_ids
    evidence: list[dict]                      # evidence manifest entries so far
    confidence: dict | None                   # overall, completeness, components
    clauses: list[dict]
    dossier_draft: dict | None
    dossier_id: str | None
    narrative_mode: Literal["LLM","TEMPLATE"] | None
    directives: list[dict]                    # investigator directives queue
    attempts: dict[str,int]                   # per-node attempt counters
    flags: list[str]                          # e.g. "PARTIAL_ATTRIBUTION","LLM_UNAVAILABLE"
    errors: list[dict]
    review: dict | None                       # status, reviewer, comment
```

### 5.3 State graph

```mermaid
stateDiagram-v2
  [*] --> OPENED: case.trigger
  OPENED --> ENRICHING: dedupe/merge check passed
  ENRICHING --> ALIGNED: market_slice & social_slice ok
  ENRICHING --> ENRICHING: retry (≤2) on timeout
  ENRICHING --> FAILED: both slices unavailable after retries
  ALIGNED --> ATTRIBUTING: p<0.01 and xcorr_peak>=0.5
  ALIGNED --> WATCHLIST: alignment weak (peak<0.5 or p>=0.01)
  ATTRIBUTING --> ASSESSING: attribution ok
  ATTRIBUTING --> ATTRIBUTING: retry with WIDEN_WINDOW (≤2)
  ATTRIBUTING --> ASSESSING: timeout → flag PARTIAL_ATTRIBUTION
  ASSESSING --> ATTRIBUTING: confidence<0.60 and widen_count<2
  ASSESSING --> CLOSED_NO_ACTION: confidence<0.40 after loops
  ASSESSING --> DRAFTING: confidence>=0.40
  DRAFTING --> VALIDATING: draft produced (LLM or TEMPLATE)
  VALIDATING --> DRAFTING: uncited claims / schema errors (≤2) → force TEMPLATE on 3rd
  VALIDATING --> SIGNING: valid
  SIGNING --> PENDING_REVIEW: signed + ledgered
  SIGNING --> FAILED: signer unavailable after 3 tries (alert)
  PENDING_REVIEW --> APPROVED: human APPROVED
  PENDING_REVIEW --> REJECTED: human REJECTED
  PENDING_REVIEW --> REWORK: human REWORK
  REWORK --> ATTRIBUTING: directive FORCE_REATTRIBUTION / WIDEN_WINDOW / EXCLUDE_ACCOUNT
  REWORK --> DRAFTING: comment-only edits
  APPROVED --> PUBLISHED: final re-sign with human_review included
  WATCHLIST --> OPENED: new trigger on same symbol within 60 min
  PUBLISHED --> [*]
  REJECTED --> [*]
  CLOSED_NO_ACTION --> [*]
  FAILED --> [*]
```

### 5.4 Node definitions, triggers, timeouts, fallbacks

| Node (LangGraph function) | Action | Timeout | Retries | Fallback / degradation |
|---|---|---|---|---|
| `open_case` | Insert `cases` row, check overlap (same symbol & windows overlap ≥ 50 %) → merge into existing case else create; emit `case.events` | 5 s | 0 | If overlap → append anomaly to existing case, end run |
| `enrich` | Parallel fan-out: `REQUEST_MARKET_SLICE` to QTA, `REQUEST_SOCIAL_SLICE` to SIA (`asyncio.gather`) | 30 s each | 2 (exp. backoff 2 s, 4 s) | One slice missing → proceed with flag `MISSING_MARKET_SLICE` / `MISSING_SOCIAL_SLICE`, lower completeness; both missing → `FAILED` |
| `align` | `REQUEST_ALIGNMENT` to Alignment Engine for case window (full-resolution, 1000 shuffles) | 45 s | 1 | On failure use trigger anomaly metrics, flag `ALIGNMENT_FROM_TRIGGER` |
| `route_after_align` (conditional edge) | If `p<0.01 and xcorr_peak≥0.5` → attribute else `WATCHLIST` | — | — | — |
| `attribute` | `REQUEST_ATTRIBUTION` to CAA with `params` (window, directives) | 90 s | 1 | Timeout → keep partial graph results from continuous loader, set `PARTIAL_ATTRIBUTION`; Neo4j down → buffer, run `NetworkX` attribution on SQL slice (`ATTRIBUTION_SQL_ONLY`) |
| `assess` | Compute `confidence` (§7.6), completeness, clause mapping (`regulatory_clauses.yaml`) | 10 s | 0 | If `confidence.overall < 0.60` and `window.widen_count < 2` → widen window ±50 % and loop to `attribute`; if `< 0.40` → `CLOSED_NO_ACTION` |
| `draft` | Evidence capture (calls `evidence_engine.capture`) then narrative: LLM structured draft → else template renderer | 60 s | 2 | LLM unavailable/invalid → deterministic `TemplateNarrator`; flag `LLM_UNAVAILABLE`; set `narrative_mode` |
| `validate` | JSON-Schema validation; citation checker (every sentence in `executive_summary` and each `timeline[].description` has ≥ 1 resolvable `evidence_id`); numeric consistency checks (volumes sum, timestamps within window) | 10 s | 2 loops back to `draft` | 3rd failure → force `TemplateNarrator` |
| `sign` | `evidence_engine.sign(dossier)` → JCS, SHA-256, Ed25519, ledger append, PDF render, bundle | 60 s | 3 | Signer failure → `FAILED` + alert `health.events` (`SIGNER_DOWN`) |
| `await_review` | LangGraph `interrupt()`; resumes on API call `POST /api/v1/cases/{id}/review` | ∞ (SLA alert at 24 h) | — | — |
| `publish` | Re-sign with `human_review` populated; new dossier version; status `PUBLISHED` | 60 s | 3 | As `sign` |

**Checkpointing & idempotency:** `PostgresSaver` with `thread_id = case_id`. Every side-effecting node derives an `idempotency_key = sha256(case_id|node|attempt_group|canonical(inputs))`; downstream stores (`evidence_objects` PK, `dossiers` UNIQUE(case_id,version), ledger entries keyed by `subject_sha256`+type) ignore duplicates, so re-execution after crash does not duplicate effects (AC-ORC-02).

**Investigator directives:** `POST /api/v1/cases/{id}/directives` pushes into `state.directives` and, if the case is in `PENDING_REVIEW` or `REWORK`, resumes the graph at `attribute` (for `WIDEN_WINDOW|EXCLUDE_ACCOUNT|FORCE_REATTRIBUTION`).

### 5.5 Orchestrator skeleton (normative structure)

```python
# services/agents/orchestrator/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import interrupt

def build_graph(deps: Deps, checkpointer: AsyncPostgresSaver):
    g = StateGraph(CaseState)
    g.add_node("open_case", nodes.open_case(deps))
    g.add_node("enrich", nodes.enrich(deps))
    g.add_node("align", nodes.align(deps))
    g.add_node("attribute", nodes.attribute(deps))
    g.add_node("assess", nodes.assess(deps))
    g.add_node("draft", nodes.draft(deps))
    g.add_node("validate", nodes.validate(deps))
    g.add_node("sign", nodes.sign(deps))
    g.add_node("await_review", nodes.await_review(deps))   # calls interrupt()
    g.add_node("publish", nodes.publish(deps))
    g.set_entry_point("open_case")
    g.add_conditional_edges("open_case", routes.after_open, {"enrich": "enrich", "merged": END})
    g.add_conditional_edges("enrich", routes.after_enrich, {"align": "align", "failed": END})
    g.add_conditional_edges("align", routes.after_align, {"attribute": "attribute", "watchlist": END})
    g.add_edge("attribute", "assess")
    g.add_conditional_edges("assess", routes.after_assess, {"attribute": "attribute", "draft": "draft", "close": END})
    g.add_edge("draft", "validate")
    g.add_conditional_edges("validate", routes.after_validate, {"draft": "draft", "sign": "sign"})
    g.add_conditional_edges("sign", routes.after_sign, {"await_review": "await_review", "failed": END})
    g.add_conditional_edges("await_review", routes.after_review,
        {"publish": "publish", "rejected": END, "rework_attr": "attribute", "rework_draft": "draft"})
    g.add_edge("publish", END)
    return g.compile(checkpointer=checkpointer)
```
The orchestrator process consumes `case.trigger` (group `orchestrator`), starts `graph.ainvoke(initial_state, config={"configurable":{"thread_id": case_id}})` as an asyncio task (max `ORCH_MAX_CONCURRENT_CASES=8`), and exposes an internal HTTP endpoint `POST /internal/resume/{case_id}` used by the API for human actions/directives.

---

## 6. Graph Schema & Cypher Queries

### 6.1 Nodes

| Label | Key property (unique) | Other properties |
|---|---|---|
| `Trader` | `account_id` | `first_seen_ms`, `last_seen_ms`, `kyc_phone_hash?`, `kyc_bank_hash?`, `kyc_addr_hash?`, `is_synthetic` |
| `Broker` | `broker_id` | `name?` |
| `Ticker` | `symbol` | `exchange`, `segment`, `isin?` |
| `Channel` | `channel_key` (`platform:channel_id`) | `platform`, `channel_id`, `name`, `visibility`, `member_count?` |
| `Device` | `device_fp` | `first_seen_ms`, `last_seen_ms` |
| `NetworkFingerprint` | `fp_key` (`ip_hash|asn|api_client_id`) | `ip_hash`, `asn`, `api_client_id` |
| `Handle` | `author_id` | `platform`, `first_seen_ms` |
| `Entity` | `entity_id` | `ring_score`, `case_id`, `created_at_ms`, `member_count` |
| `Case` | `case_id` | `symbol`, `status` |

### 6.2 Relationships

| Relationship | Pattern | Properties |
|---|---|---|
| `TRADED_WITH` | `(seller:Trader)-[:TRADED_WITH]->(buyer:Trader)` (direction = share flow) | `ticker`, `ts` (bucket start, epoch ms), `ts_end`, `qty`, `notional`, `n_trades`, `trade_ids` (first 5) |
| `ROUTED_THROUGH` | `(Trader)-[:ROUTED_THROUGH]->(Broker)` | `gateway_id`, `share` (0–1 of trader's volume in window), `n_orders`, `first_ms`, `last_ms` |
| `COMMUNICATED_ON` | `(Handle)-[:COMMUNICATED_ON]->(Channel)` | `n_messages`, `first_ms`, `last_ms` |
| `PROMOTED` | `(Channel)-[:PROMOTED]->(Ticker)` | `first_ms`, `last_ms`, `n_signals`, `cta_mix` (map), `peak_hype` |
| `USES_DEVICE` | `(Trader)-[:USES_DEVICE]->(Device)` | `n_orders`, `first_ms`, `last_ms` |
| `HAS_FINGERPRINT` | `(Trader)-[:HAS_FINGERPRINT]->(NetworkFingerprint)` | `n_orders`, `first_ms`, `last_ms` |
| `SYNCHRONIZED_WITH` | `(Trader)-[:SYNCHRONIZED_WITH]-(Trader)` (undirected semantics; stored a→b with `elementId(a) < elementId(b)`) | `ticker`, `window_start_ms`, `window_end_ms`, `co_orders`, `median_dt_ms`, `p_value`, `case_id` |
| `REACTED_TO` | `(Trader)-[:REACTED_TO]->(Channel)` | `ticker`, `n_reactions`, `median_latency_ms`, `null_median_latency_ms`, `p_value`, `confidence` |
| `LINKED_TO` | `(Handle)-[:LINKED_TO]->(Trader)` — **lawful-access data only** | `method`, `confidence`, `evidence_ref` |
| `LINKED` | `(Trader)-[:LINKED]-(Trader)` (case-scoped consolidated link) | `case_id`, `weight`, `confidence`, `methods` (list), `evidence_ids` |
| `CONTROLLED_BY` | `(Trader)-[:CONTROLLED_BY]->(Entity)` | `case_id`, `confidence` |
| `SUBJECT_OF` | `(Entity)-[:SUBJECT_OF]->(Case)` | — |

### 6.3 Constraints & indexes (`migrations/neo4j/001_constraints.cypher`)

```cypher
CREATE CONSTRAINT trader_pk   IF NOT EXISTS FOR (n:Trader)  REQUIRE n.account_id IS UNIQUE;
CREATE CONSTRAINT broker_pk   IF NOT EXISTS FOR (n:Broker)  REQUIRE n.broker_id  IS UNIQUE;
CREATE CONSTRAINT ticker_pk   IF NOT EXISTS FOR (n:Ticker)  REQUIRE n.symbol     IS UNIQUE;
CREATE CONSTRAINT channel_pk  IF NOT EXISTS FOR (n:Channel) REQUIRE n.channel_key IS UNIQUE;
CREATE CONSTRAINT device_pk   IF NOT EXISTS FOR (n:Device)  REQUIRE n.device_fp  IS UNIQUE;
CREATE CONSTRAINT netfp_pk    IF NOT EXISTS FOR (n:NetworkFingerprint) REQUIRE n.fp_key IS UNIQUE;
CREATE CONSTRAINT handle_pk   IF NOT EXISTS FOR (n:Handle)  REQUIRE n.author_id  IS UNIQUE;
CREATE CONSTRAINT entity_pk   IF NOT EXISTS FOR (n:Entity)  REQUIRE n.entity_id  IS UNIQUE;
CREATE CONSTRAINT case_pk     IF NOT EXISTS FOR (n:Case)    REQUIRE n.case_id    IS UNIQUE;
CREATE INDEX traded_ticker_ts IF NOT EXISTS FOR ()-[r:TRADED_WITH]-() ON (r.ticker, r.ts);
CREATE INDEX sync_ticker      IF NOT EXISTS FOR ()-[r:SYNCHRONIZED_WITH]-() ON (r.ticker, r.window_start_ms);
CREATE INDEX linked_case      IF NOT EXISTS FOR ()-[r:LINKED]-() ON (r.case_id);
```

### 6.4 Core Cypher queries (parameterized; stored in `services/agents/attribution/src/attribution/queries/*.cypher`)

**Q1 — Circular wash-trading cycles (length 2–6, time-ordered, quantity-matched, distinct accounts)**
`queries/wash_cycles.cypher`
```cypher
// params: $ticker, $t0 (epoch ms), $t1, $max_cycle_ms (e.g. 900000), $qty_tol (e.g. 0.05), $min_len (2), $max_len (6), $candidates (list of account_id)
MATCH p = (a:Trader)-[rels:TRADED_WITH*2..6 {ticker: $ticker}]->(a)
WHERE a.account_id IN $candidates
  AND size(rels) >= $min_len AND size(rels) <= $max_len
  AND rels[0].ts >= $t0 AND rels[-1].ts_end <= $t1
  AND (rels[-1].ts_end - rels[0].ts) <= $max_cycle_ms
  AND ALL(i IN range(0, size(rels) - 2) WHERE rels[i].ts <= rels[i+1].ts)
  AND ALL(r IN rels WHERE abs(r.qty - rels[0].qty) <= $qty_tol * rels[0].qty)
WITH p, rels, a, nodes(p)[0..-1] AS ns
WHERE size(ns) = size(apoc.coll.toSet(ns))                       // no repeated intermediate accounts
  AND ALL(n IN ns WHERE elementId(a) <= elementId(n))             // canonical rotation → report each cycle once
RETURN [n IN ns | n.account_id]                       AS accounts,
       size(rels)                                     AS length,
       rels[0].qty                                    AS lead_qty,
       reduce(v = 0, r IN rels | v + r.qty)           AS cycle_volume,
       rels[0].ts                                     AS start_ms,
       rels[-1].ts_end                                AS end_ms,
       [r IN rels | r.trade_ids[0]]                   AS evidence_trade_ids
ORDER BY cycle_volume DESC
LIMIT 500;
```

**Q2 — Coordinated volume loops: pairs/groups with repeated synchronized orders (significant)**
`queries/sync_pairs.cypher`
```cypher
// params: $ticker, $t0, $t1, $max_p (0.01), $min_windows (3)
MATCH (a:Trader)-[s:SYNCHRONIZED_WITH {ticker: $ticker}]->(b:Trader)
WHERE s.window_start_ms >= $t0 AND s.window_end_ms <= $t1 AND s.p_value < $max_p
WITH a, b, count(s) AS windows, sum(s.co_orders) AS co_orders, min(s.p_value) AS best_p, avg(s.median_dt_ms) AS avg_dt_ms
WHERE windows >= $min_windows
RETURN a.account_id AS a, b.account_id AS b, windows, co_orders, best_p, avg_dt_ms
ORDER BY co_orders DESC;
```

**Q3 — Shared device / network fingerprint clusters**
`queries/shared_fingerprints.cypher`
```cypher
// params: $accounts
MATCH (t:Trader)-[u:USES_DEVICE]->(d:Device)
WHERE t.account_id IN $accounts
WITH d, collect(DISTINCT t.account_id) AS accounts, sum(u.n_orders) AS n_orders
WHERE size(accounts) >= 2
RETURN 'SHARED_DEVICE' AS method, d.device_fp AS key, accounts, n_orders
UNION
MATCH (t:Trader)-[h:HAS_FINGERPRINT]->(f:NetworkFingerprint)
WHERE t.account_id IN $accounts
WITH f, collect(DISTINCT t.account_id) AS accounts, sum(h.n_orders) AS n_orders
WHERE size(accounts) >= 2
RETURN 'SHARED_NETWORK' AS method, f.fp_key AS key, accounts, n_orders;
```

**Q4 — Broker pathway concentration**
`queries/broker_pathways.cypher`
```cypher
// params: $accounts, $min_share (0.8), $min_group (3)
MATCH (t:Trader)-[r:ROUTED_THROUGH]->(b:Broker)
WHERE t.account_id IN $accounts AND r.share >= $min_share
WITH b, r.gateway_id AS gw, collect(DISTINCT t.account_id) AS accounts
WHERE size(accounts) >= $min_group
RETURN b.broker_id AS broker, gw AS gateway, accounts, size(accounts) AS n;
```

**Q5 — Social-to-trader reaction links**
`queries/reaction_links.cypher`
```cypher
// params: $ticker, $min_conf (0.6)
MATCH (t:Trader)-[r:REACTED_TO {ticker: $ticker}]->(c:Channel)-[p:PROMOTED]->(k:Ticker {symbol: $ticker})
WHERE r.confidence >= $min_conf
RETURN t.account_id AS account, c.channel_key AS channel, r.n_reactions AS n,
       r.median_latency_ms AS median_latency_ms, r.null_median_latency_ms AS null_ms, r.p_value AS p,
       p.peak_hype AS peak_hype
ORDER BY r.confidence DESC;
```

**Q6 — Entity (ring) rollup for a case**
`queries/entity_rollup.cypher`
```cypher
// params: $case_id
MATCH (e:Entity {case_id: $case_id})<-[:CONTROLLED_BY]-(t:Trader)
OPTIONAL MATCH (t)-[:ROUTED_THROUGH]->(b:Broker)
OPTIONAL MATCH (t)-[:USES_DEVICE]->(d:Device)
RETURN e.entity_id AS entity_id, e.ring_score AS ring_score,
       collect(DISTINCT t.account_id) AS accounts,
       collect(DISTINCT b.broker_id)  AS brokers,
       count(DISTINCT d)              AS devices;
```

**Q7 — Case subgraph export for Cytoscape**
`queries/case_subgraph.cypher`
```cypher
// params: $case_id, $max_nodes (500)
MATCH (e:Entity {case_id: $case_id})<-[:CONTROLLED_BY]-(t:Trader)
WITH collect(DISTINCT t) AS traders LIMIT 1
UNWIND traders AS a
OPTIONAL MATCH (a)-[l:LINKED {case_id: $case_id}]-(b:Trader) WHERE b IN traders
OPTIONAL MATCH (a)-[tw:TRADED_WITH]->(c:Trader) WHERE c IN traders
OPTIONAL MATCH (a)-[:USES_DEVICE]->(d:Device)
OPTIONAL MATCH (a)-[:ROUTED_THROUGH]->(br:Broker)
RETURN a, collect(DISTINCT l) AS links, collect(DISTINCT tw) AS trades,
       collect(DISTINCT d) AS devices, collect(DISTINCT br) AS brokers
LIMIT $max_nodes;
```
The API transforms results to `{"nodes":[{"data":{"id","label","type",...}}],"edges":[{"data":{"id","source","target","type",...}}]}`.

**Writer upserts (examples)** — `queries/upsert_trade_edges.cypher`
```cypher
UNWIND $rows AS row
MERGE (s:Trader {account_id: row.seller}) ON CREATE SET s.first_seen_ms = row.ts_ms, s.is_synthetic = row.is_synthetic SET s.last_seen_ms = row.ts_ms
MERGE (b:Trader {account_id: row.buyer})  ON CREATE SET b.first_seen_ms = row.ts_ms, b.is_synthetic = row.is_synthetic SET b.last_seen_ms = row.ts_ms
MERGE (k:Ticker {symbol: row.ticker}) ON CREATE SET k.exchange = row.exchange
MERGE (s)-[e:TRADED_WITH {ticker: row.ticker, ts: row.bucket_ms}]->(b)
  ON CREATE SET e.qty = row.qty, e.notional = row.notional, e.n_trades = row.n, e.ts_end = row.ts_end_ms, e.trade_ids = row.trade_ids
  ON MATCH  SET e.qty = e.qty + row.qty, e.notional = e.notional + row.notional, e.n_trades = e.n_trades + row.n, e.ts_end = row.ts_end_ms;
```
(Use deterministic per-batch aggregation before the write; to remain idempotent on replay, include `row.batch_id` in an `applied_batches` set property on the edge and skip if present.)

---

## 7. Detection Algorithms & Formulas (normative)

### 7.1 Quant detectors

**Common:** per-symbol state; time is *event time* (`ts_exchange`); bars are 5-s sums unless stated. Robust z: `z = 0.6745·(x − median) / MAD` (floor MAD at `1e-9` and at `0.1·median` to avoid explosions on illiquid symbols).

| Detector | Algorithm | Default parameters (`config/detectors.yaml`, per tier) |
|---|---|---|
| `VolumeSpikeDetector` | Maintain ring buffer of 5-s volumes over 30 min (360 bins) → median/MAD; apply seasonality multiplier `s(tod)` from `symbol_profile` (fallback 1.0). Fire when `z ≥ z_thr` for `k` consecutive bins. Score = `min(1, z / 12)`. | micro: `z_thr=4.0,k=3`; mid: `5.0,3`; large: `6.0,4` |
| `SpreadDepthDetector` | `rel_spread = (ask−bid)/mid`; baseline median over 15 min; fire `SPREAD_WIDENING` if `rel_spread ≥ 3×median`; `imbalance = (Σbid_qty₅ − Σask_qty₅)/(Σbid_qty₅ + Σask_qty₅)`, fire `DEPTH_IMBALANCE` if `|imbalance| ≥ 0.7` for ≥ 10 s. | as PRD FR-QTA-02 |
| `SpoofingLayeringDetector` | Per account sliding 2-s window on L3: `orders_new ≥ 5`, `cancel_ratio = cancels/new ≥ 0.9`, `Σqty_new ≥ 5×median_order_qty(symbol)`, and an opposite-side `TRADE` by the same account within 1 s after the first cancel. Score = `0.4·min(1,cancel_ratio) + 0.3·min(1, Σqty/(10·median)) + 0.3·(1 if opp_exec else 0)`. | `window_ms=2000, min_orders=5, cancel_ratio=0.9, qty_mult=5, exec_ms=1000` |
| `WashCycleDetector` | Streaming round-trip search: keep per-symbol deque of trades in `cycle_window_s=900`; maintain directed multigraph `seller→buyer` of trades; on each trade try DFS (depth ≤ 4) to return to the seller; accept if cycle qty within `qty_tol=0.05` of leading qty and price within `price_tol=0.005`. Also detect **2-cycles** (A↔B) and **self-matched** (`buyer_account == seller_account` or same `device_fp` on both sides). Score = `min(1, 0.5 + 0.1·len + 0.4·(matched_qty/total_volume_in_window))`. | `cycle_window_s=900, qty_tol=0.05, price_tol=0.005, max_len=4` (graph query extends to 6) |
| `SynchronizedOrdersDetector` | Cluster same-side `NEW` orders per symbol into 500-ms bins; for bins with ≥ 3 distinct accounts count `co_orders` per account pair; null: Poisson with λ from each account's order rate; p-value via Poisson tail on pair co-occurrence count; fire when pair appears in ≥ 3 bins in 10 min with `p < 0.01` (Bonferroni over active pairs). Writes `SYNCHRONIZED_WITH` graph updates. | `bin_ms=500, min_accounts=3, min_bins=3, window_s=600, p=0.01` |
| `PriceJumpDetector` | 1-min log returns vs 1-h robust σ (MAD·1.4826); fire when `|r| ≥ 5σ`. Score = `min(1, |r|/(10σ))`. | `sigma_thr=5` |

Severity mapping from score: `<0.4 LOW`, `<0.7 MEDIUM`, `<0.9 HIGH`, else `CRITICAL`.

### 7.2 Hype score (`config/hype_weights.yaml`)
Window `W = 60 s`, step `5 s`, per ticker, over `SocialSignal` records with `ticker_confidence ≥ 0.6`.

- `σ(x) = 1/(1+e^{-x})`
- `f_rate = σ((z_rate − 3)/1.0)`, where `z_rate` is the z-score of the message count in the last 5 s vs. an EWMA mean/variance (α=0.02, baseline horizon ≈ 1 h; floor σ at 0.5 msgs).
- `f_auth = σ((z_auth − 3)/1.0)`, z-score of *unique new authors* in W.
- `f_cta = Σ_i cta_confidence_i · 1[cta_class_i ≠ NEUTRAL] / N`.
- `f_dup = (messages in near-dup clusters of size ≥ 3) / N`.
- `f_urg = mean(urgency_i)`.
- `f_xch = min(1, (distinct_channels − 1)/3)`.

`hype_score = 100 · (0.25·f_rate + 0.15·f_auth + 0.20·f_cta + 0.15·f_dup + 0.10·f_urg + 0.15·f_xch)`; if `N < 5` set `hype_score = min(hype_score, 20)`.
`HYPE_BURST`: `hype_score ≥ 70` continuously for ≥ 30 s. `NEAR_DUPLICATE_CAMPAIGN`: cluster with ≥ 5 messages from ≥ 3 distinct authors in ≥ 2 channels within 5 min.

### 7.3 Cross-modal alignment
Inputs (1-s grid, last 3600 s): `h(t)` hype score, `v(t)` volume robust-z (from `bars_1s`, log1p-transformed then detrended by 5-min rolling median), `a(t)` `|return|`.
1. Standardize `h`, `v`; compute normalized cross-correlation `ρ(τ)` for `τ ∈ [−120, +1800]` s via FFT (`scipy.signal.correlate`, mode `full`, divided by `n·σ_hσ_v`). Positive `τ` ⇒ social leads market.
2. `best_lag_s = argmax_τ ρ(τ)`, `xcorr_peak = ρ(best_lag_s)`.
3. p-value: circularly block-shuffle `v` (block 60 s) `B=500` (1000 in case-run) times, recompute `max_τ ρ`; `p = (1 + #{null_max ≥ xcorr_peak}) / (B + 1)`.
4. Event rule: `HYPE_BURST` followed by `VOLUME_SPIKE|PRICE_JUMP` on same ticker with `0 < Δt ≤ 900 s` also qualifies (fast path, no permutation test needed).
5. Late-data handling: watermark 30 s; series recomputed from Timescale each cycle so late events are reflected.

### 7.4 Manipulation Risk Score (MRS), per ticker per minute
```
MRS = 100 · ( 0.30·hype/100
            + 0.25·min(1, volume_z/10)
            + 0.15·align            # xcorr_peak if p<0.01 else 0
            + 0.15·ring             # max ring_score of active cases for ticker, else 0
            + 0.10·price            # min(1, |ret_5m| / (5·σ_1h))
            + 0.05·micro )          # max score of SPREAD/DEPTH/SPOOFING anomalies in last 5 min
```
Components persisted in `mrs_1m.components`.

### 7.5 Attribution link evidence & ring score
For a pair of accounts `(i,j)` each evidence method `m` yields strength `s_m ∈ [0,1]`:

| Method (`methods[]`) | Weight `w_m` (`config/attribution_weights.yaml`) | Strength `s_m` |
|---|---|---|
| `SHARED_KYC` | 0.95 | 1 if any KYC hash equal |
| `SHARED_DEVICE` | 0.90 | `min(1, 0.6 + 0.1·shared_device_count)` |
| `CIRCULAR_CYCLE` | 0.85 | `min(1, cycles_together / 3)` |
| `SYNCHRONIZED_ORDERS` | 0.70 | `1 − best_p·100` clipped to [0,1] |
| `SHARED_NETWORK` | 0.60 | 1 if same `ip_hash`; 0.5 if same ASN **and** same `api_client_id` |
| `LATENCY_SIGNATURE` | 0.50 | KS p-value mapped: `min(1, p_ks/0.5)` (requires ≥ 50 samples each) |
| `REACTION_LATENCY` | 0.50 | `1 − p_react` where both reacted to same CTA set |
| `BROKER_PATHWAY` | 0.40 | 1 if both ≥ 80 % share via same `(broker, gateway)` |

- **Pair confidence (noisy-OR):** `conf_ij = 1 − Π_m (1 − w_m·s_m)`.
- Create `LINKED` edge if `conf_ij ≥ 0.60`; edge weight = `conf_ij`. Investigator `CONFIRM` sets the edge's `conf = max(conf, 0.95)`; `REJECT` removes the edge and records a veto so it is not recreated.
- **Entities:** connected components (then Louvain refinement for > 40 nodes). For entity `E`: let `S_m = max over pairs in E of s_m`; `ring_score(E) = min(0.99, 1 − Π_m (1 − w_m·S_m))`, multiplied by `min(1, 0.5 + 2·entity_volume_share)` where `entity_volume_share` = entity volume / symbol volume in window.
- Accounts attached to an entity with only `conf < 0.60` links are listed as **leads**, not findings (PRD G-2).
- Reaction analysis (`REACTED_TO`): for each CTA message time `t_c` and trader `i`, `latency = t_first_aggressive_order_after(t_c) − t_c`; null = same statistic for 200 random reference times drawn from the same window; one-sided Mann–Whitney U test; link if `p < 0.01` and `n ≥ 3`.

### 7.6 Case confidence
```
alignment_conf  = xcorr_peak · (1 − p_value)                       (0 if no alignment)
attribution_conf= mean(top-3 ring_score) (0 if none)
market_conf     = min(1, 0.5·max_anomaly_score + 0.5·suspect_volume_ratio·2)
completeness    = (# present of {trades, social, alignment, attribution, clauses, raw_hashes}) / 6
overall         = 0.30·alignment_conf + 0.35·attribution_conf + 0.20·market_conf + 0.15·completeness
```
`confidence.components` stores all four values; `limitations[]` MUST list each missing class and active flags.

### 7.7 Clause registry (`config/regulatory_clauses.yaml`) — structure
```yaml
- clause_id: "SEBI-PFUTP-R4(2)"      # advisory mapping; legal_review_required must remain true
  regime: SEBI
  title: "PFUTP Regulations, 2003 — Reg. 4(2) (examples of manipulative, fraudulent and unfair trade practices)"
  finding_types: [WASH_CYCLE, CIRCULAR_RING, COORDINATED_VOLUME_LOOP, PRICE_JUMP]
  rationale_template: "Matched/circular trades among {n_accounts} linked accounts representing {suspect_ratio:.0%} of volume are consistent with creating a false or misleading appearance of trading."
  legal_review_required: true
- clause_id: "SEBI-PFUTP-R3"
  regime: SEBI
  title: "PFUTP Regulations, 2003 — Reg. 3 (prohibition of certain dealings in securities)"
  finding_types: [HYPE_BURST, CROSS_MODAL_ALIGNMENT, NEAR_DUPLICATE_CAMPAIGN]
  legal_review_required: true
- clause_id: "SEC-EA-9(a)(1)"
  regime: SEC
  title: "Securities Exchange Act of 1934 §9(a)(1) — wash sales / matched orders"
  finding_types: [WASH_CYCLE, CIRCULAR_RING]
  legal_review_required: true
- clause_id: "SEC-EA-9(a)(2)"
  regime: SEC
  title: "Securities Exchange Act of 1934 §9(a)(2) — series of transactions raising/depressing price"
  finding_types: [VOLUME_SPIKE, PRICE_JUMP, COORDINATED_VOLUME_LOOP, SYNCHRONIZED_ORDERS]
  legal_review_required: true
- clause_id: "SEC-EA-10b-Rule10b-5"
  regime: SEC
  title: "Exchange Act §10(b) and Rule 10b-5 — manipulative and deceptive devices"
  finding_types: [HYPE_BURST, CROSS_MODAL_ALIGNMENT, SPOOFING_LAYERING]
  legal_review_required: true
```
The clause mapper selects entries whose `finding_types` intersect the case's anomaly types and whose jurisdiction matches `dossier.jurisdiction`; rationale text is rendered from `rationale_template` using case metrics (never free-form LLM output). Operators MUST have counsel review and extend this file (e.g., sub-clause level citations) before operational use.

---

## 8. API Specification (FastAPI, `services/api`)

Base path `/api/v1`. All responses JSON unless stated. Errors: RFC 7807 `application/problem+json`. Pagination: `?limit=50&cursor=…`. RBAC in brackets: **I**=investigator, **C**=compliance_officer, **A**=admin, **R**=auditor_readonly.

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/healthz`, `/readyz`, `/metrics` | public | Probes/metrics |
| POST | `/auth/dev-token` | dev only | Issue HS256 JWT `{sub, role}` (disabled when `ENV=prod`) |
| GET | `/me` | all | Current user & role |
| GET | `/symbols/heatmap` | I,C,A,R | Latest MRS per symbol `[{symbol, mrs, hype, volume_z, price, ts}]` |
| GET | `/symbols/{symbol}/series?from&to&res=1s\|5s\|1m` | I,C,A,R | Aligned series: `bars`, `hype`, `l2_metrics`, `mrs` |
| GET | `/anomalies?symbol&type&from&to&min_score` | I,C,A,R | Anomaly events |
| GET | `/social/signals?ticker&from&to&channel` | I,C,A,R | Signals (text redacted unless role I/C) |
| GET | `/cases?status&symbol&min_mrs&limit&cursor` | I,C,A,R | List cases |
| GET | `/cases/{case_id}` | I,C,A,R | Case detail incl. state summary, timeline, flags |
| GET | `/cases/{case_id}/timeline` | I,C,A,R | Unified chronological events `[ {ts, track, description, evidence_ids} ]` |
| GET | `/cases/{case_id}/graph?max_nodes=500&min_conf=0.6` | I,C,A,R | Cytoscape elements JSON |
| GET | `/cases/{case_id}/evidence` | I,C,A,R | Evidence manifest entries |
| GET | `/evidence/{evidence_id}/download` | I,C,A | Stream evidence file (presigned redirect) |
| POST | `/cases/{case_id}/directives` | I,C | Body `{type: WIDEN_WINDOW\|EXCLUDE_ACCOUNT\|FORCE_REATTRIBUTION, params:{...}}` → 202 |
| POST | `/cases/{case_id}/links/feedback` | I,C | Body `{a_account,b_account,verdict:CONFIRM\|REJECT,comment}` |
| POST | `/cases/{case_id}/submit` | I | Move `REWORK`/draft case to review queue if eligible → 202 |
| POST | `/cases/{case_id}/review` | C | Body `{status: APPROVED\|REJECTED\|REWORK, comment}` → resumes graph; 409 if state not `PENDING_REVIEW` |
| GET | `/cases/{case_id}/dossiers` | I,C,A,R | Versions list |
| GET | `/dossiers/{dossier_id}` | I,C,A,R | Dossier JSON |
| GET | `/dossiers/{dossier_id}/pdf` | I,C,A,R | `application/pdf` |
| GET | `/dossiers/{dossier_id}/bundle` | C,A | ZIP bundle |
| GET | `/dossiers/{dossier_id}/verify` | all | Live verification result (see below) |
| POST | `/verify` | all | Multipart bundle upload → verification result |
| POST | `/accounts/{account_id}/reveal` | C | Re-identification via KMS/pepper registry; writes audit + ledger |
| GET | `/ledger?from_id&limit` | C,A,R | Ledger entries |
| GET | `/ledger/verify?from_id&to_id` | C,A,R | Recompute hash chain |
| GET | `/admin/health` | A,I | Aggregated service health, consumer lag, latency percentiles |
| POST | `/sim/scenarios/{scenario_id}/start` · `/stop` · GET `/sim/status` | A (dev only) | Proxy to simulator |
| WS | `/ws/v1/stream?topics=heatmap,anomalies,cases,hype:{ticker}` | all | JSON frames `{topic, ts, data}`; server heartbeat 15 s |

**Verification result schema**
```json
{
  "valid": true,
  "dossier_id": "…","version": 2,
  "checks": [
    {"name":"SCHEMA_VALID","ok":true},
    {"name":"EVIDENCE_HASHES","ok":true,"checked":14},
    {"name":"MERKLE_ROOT","ok":true},
    {"name":"LEDGER_CHAIN","ok":true,"entries":37},
    {"name":"SIGNATURE","ok":true,"key_id":"dev-2026-01"},
    {"name":"HUMAN_REVIEW_PRESENT","ok":true}
  ],
  "failed": []
}
```
Failure `failed` entries use names `HASH_MISMATCH`, `MERKLE_MISMATCH`, `LEDGER_CHAIN_BROKEN`, `SIGNATURE_INVALID`, `SCHEMA_INVALID`.

WebSocket fan-out: the API runs a Kafka consumer group per instance (`api-ws-{instance}`) on `anomaly.*`, `case.events`, and Redis `mrs:*` poll (1 s) → broadcast to subscribed sockets.

---

## 9. Evidence Generation Engine (`services/evidence_engine`)

### 9.1 Capture
`capture(case_id, window, kinds)` produces evidence objects:
- `TRADE_SLICE`, `L2_SLICE`, `L3_SLICE`, `SOCIAL_SLICE` — NDJSON.zst exports from Timescale (ordered by `(ts, seq)`; deterministic serialization via `orjson` with `OPT_SORT_KEYS`).
- `ANOMALY_EVENT` — one JSON per anomaly referenced.
- `GRAPH_EXPORT` — canonical JSON of the case subgraph (sorted nodes/edges).
- `CHART_IMAGE` — matplotlib PNG (fixed DPI, no embedded timestamps) of aligned timeline.
- `LLM_TRACE` — prompts/responses (hashed and stored encrypted; raw text stored only if `LLM_TRACE_STORE_TEXT=true`).
- `CONFIG_SNAPSHOT` — `detectors.yaml`, `hype_weights.yaml`, `attribution_weights.yaml`, `regulatory_clauses.yaml`, git SHA, package versions.

Each object → `sha256` → upload to `vigil-evidence/{case_id}/{evidence_id}` → insert `evidence_objects` → ledger entry `EVIDENCE` (`subject_sha256 = sha256`). `evidence_id` format: `EV-{TYPE}-{first 12 hex of sha256}`.

### 9.2 Ledger append (single writer, serialized)
```sql
BEGIN;
SELECT pg_advisory_xact_lock(727001);                         -- serialize appenders
SELECT entry_hash INTO prev FROM evidence_ledger ORDER BY entry_id DESC LIMIT 1;  -- or 64 zeros
-- compute entry_hash in app code per §3.3 formula, INSERT, COMMIT
```
**Daily anchor** (cron in `evidence_engine`, 00:05 UTC): Merkle root over that day's `entry_hash` values → `vigil-anchors/daily/YYYY-MM-DD.json` + ledger entry `ANCHOR`; optional RFC 3161 request to `TSA_URL`, token stored in the anchor JSON.

### 9.3 Merkle tree (RFC 6962-style domain separation)
- Leaf = `SHA256(0x00 ‖ sha256_bytes_of_evidence)`; leaves ordered by `evidence_id` ascending.
- Node = `SHA256(0x01 ‖ left ‖ right)`; if odd count at a level, promote the last node unchanged.
- `merkle_root` hex goes into the dossier; per-leaf inclusion proofs are stored in `bundle/proofs.json`.

### 9.4 Dossier signing
1. Build dossier dict with `signature` omitted.
2. `canon = rfc8785.dumps(dossier)` (UTF-8 bytes).
3. `digest = SHA256(canon)`.
4. `sig = signer.sign(digest)` → Ed25519 over the 32-byte digest.
5. Insert `signature = {alg:"Ed25519", key_id, canonicalization:"RFC8785-JCS", digest_sha256: hex(digest), value_b64, signed_at}`.
6. Ledger entry `DOSSIER` (`subject_sha256 = digest`), then store JSON, PDF, `.sig`, bundle.

```python
class Signer(Protocol):
    key_id: str
    def sign(self, digest: bytes) -> bytes: ...
    def public_key_pem(self) -> str: ...
class FileEd25519Signer(Signer): ...        # dev: keys/dev_ed25519.pem (generated by scripts/gen_dev_keys.sh)
class VaultTransitSigner(Signer): ...       # prod: HashiCorp Vault transit ed25519 (stub in MVP)
```
Key registry: `signing_keys` table; keys never deleted; retired keys retain verification ability.

### 9.5 PDF rendering
Jinja2 template `templates/dossier.html.j2` → WeasyPrint. Sections: (1) Cover + integrity box (dossier_id, version, digest, key_id, QR → `{PUBLIC_BASE_URL}/dossiers/{id}`), (2) Executive summary, (3) Chronological timeline table (social vs market tracks), (4) Market evidence (+chart), (5) Social evidence, (6) Attribution (ring table, graph snapshot image), (7) Violated clauses (with advisory legend), (8) Confidence & limitations, (9) Evidence manifest (id, type, sha256), (10) Human review block, (11) Certificate-of-integrity template page (jurisdiction-specific wording from `templates/certificates/{SEBI_IN,SEC_US,GENERIC}.md.j2`, flagged as requiring legal review). PDF bytes hashed and added to the manifest as non-signed attachment record in the bundle (`bundle/pdf.sha256`).

### 9.6 Bundle layout (`bundle.zip`)
```
dossier.json            # canonical (JCS) bytes
dossier.sig             # base64 signature
dossier.pdf
manifest.json           # evidence_manifest + merkle_root
proofs.json             # Merkle inclusion proofs
ledger_proof.json       # contiguous ledger rows covering all referenced entries (+ anchor refs)
evidence/…              # every evidence object
pubkey.pem
VERIFY.md               # human instructions
```

### 9.7 Verifier (`services/verifier`, importable by API; CLI `vigil-verify`)
Steps (all must pass): (1) JSON-Schema validation; (2) recompute SHA-256 of every evidence file vs `manifest`; (3) rebuild Merkle root and compare; (4) verify `ledger_proof.json` chain linkage and that `ledger_anchor.entry_hash` is included; (5) recompute JCS digest and verify Ed25519 signature with `pubkey.pem` (or registry key). CLI: `vigil-verify bundle.zip --pubkey pubkey.pem [--json]`; exit 0 only if all checks pass. Browser-side verifier (`/verify`) re-implements steps 2–5 using WebCrypto/`@noble/ed25519` and JCS (`canonicalize` npm package).

---

## 10. Project Directory Structure

```
vigil/
├── README.md
├── PRD.md
├── ARCHITECTURE.md
├── Makefile
├── pyproject.toml                      # uv workspace root (members: libs/*, services/**)
├── uv.lock
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.override.yml         # dev: bind-mounts, hot reload
├── docker/
│   ├── python.Dockerfile               # ARG SERVICE_PATH; multi-stage uv build
│   └── frontend.Dockerfile
├── .github/workflows/ci.yml
├── config/
│   ├── detectors.yaml
│   ├── hype_weights.yaml
│   ├── attribution_weights.yaml
│   ├── cta_lexicon.yaml
│   ├── ticker_aliases.yaml
│   ├── social_channels.yaml
│   ├── regulatory_clauses.yaml
│   ├── rbac.yaml
│   └── scenarios/
│       ├── baseline_01.yaml
│       ├── pump_dump_ring_01.yaml
│       ├── wash_ring_01.yaml
│       ├── spoofing_01.yaml
│       ├── liquidity_squeeze_01.yaml
│       └── adversarial_noise_01.yaml
├── infra/
│   ├── redpanda/create_topics.sh
│   ├── postgres/init/00_extensions.sql
│   ├── neo4j/init.sh                   # waits for bolt, applies migrations/neo4j/*.cypher
│   ├── minio/init.sh                   # creates buckets
│   ├── otel/otel-collector.yaml
│   ├── prometheus/prometheus.yml
│   └── grafana/
│       ├── provisioning/{datasources,dashboards}/*.yml
│       └── dashboards/{ingest.json,agents.json,cases.json}
├── migrations/
│   ├── timescale/
│   │   ├── alembic.ini
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 0001_core_tables.py
│   │       ├── 0002_continuous_aggregates.py
│   │       ├── 0003_ledger_triggers.py
│   │       └── 0004_cases_dossiers_audit.py
│   └── neo4j/
│       ├── 001_constraints.cypher
│       └── 002_indexes.cypher
├── libs/
│   └── vigil_common/
│       ├── pyproject.toml
│       └── src/vigil_common/
│           ├── __init__.py
│           ├── config.py               # pydantic-settings Settings
│           ├── logging.py              # structlog JSON
│           ├── telemetry.py            # OTel + Prometheus helpers
│           ├── ids.py                  # uuid7, evidence_id
│           ├── timeutil.py             # ns timestamps, RFC3339
│           ├── pseudonym.py            # HMAC pseudonymization
│           ├── topics.py               # topic name constants
│           ├── kafka.py                # producer/consumer factories, batch helpers
│           ├── redis_bus.py            # AgentMessage stream client
│           ├── db.py                   # asyncpg pool, helpers
│           ├── graph.py                # neo4j async driver wrapper
│           ├── objectstore.py          # S3/MinIO client
│           ├── hashing.py              # sha256 helpers
│           ├── canonical.py            # JCS wrapper
│           ├── merkle.py
│           ├── ledger.py               # append + verify chain
│           ├── signing.py              # Signer implementations
│           ├── health.py               # /healthz /readyz /metrics app factory
│           ├── models/
│           │   ├── market.py           # TradeTick, L2Snapshot, L3OrderEvent
│           │   ├── social.py           # SocialMessage, SocialSignal
│           │   ├── anomaly.py          # AnomalyEvent
│           │   ├── case.py             # CaseStage, CaseState, CaseTrigger, CaseEvent
│           │   ├── dossier.py          # ForensicDossier & sub-models
│           │   └── agent_messages.py   # AgentMessage
│           └── schemas/                # generated *.schema.json (committed)
│               ├── trade_tick.schema.json
│               ├── l2_snapshot.schema.json
│               ├── l3_order_event.schema.json
│               ├── social_message.schema.json
│               ├── social_signal.schema.json
│               ├── anomaly_event.schema.json
│               └── forensic_dossier.schema.json
├── services/
│   ├── market_ingest/
│   │   ├── pyproject.toml
│   │   └── src/market_ingest/{main.py,adapters/{base.py,websocket.py,file_replay.py},pipeline.py,validators.py,dedupe.py,seqcheck.py}
│   ├── social_ingest/
│   │   ├── pyproject.toml
│   │   └── src/social_ingest/{main.py,adapters/{base.py,synthetic_ws.py,telegram_public.py,file_replay.py},pipeline.py,visibility.py}
│   ├── stream_sink/
│   │   ├── pyproject.toml
│   │   └── src/stream_sink/{main.py,sinks/{timescale.py,archiver.py,clickhouse_stub.py},mappers.py}
│   ├── agents/
│   │   ├── quant_telemetry/
│   │   │   ├── pyproject.toml
│   │   │   └── src/quant_telemetry/{main.py,state.py,tools.py,detectors/{base.py,volume.py,spread_depth.py,spoofing.py,wash_cycle.py,sync_orders.py,price_jump.py}}
│   │   ├── social_intel/
│   │   │   ├── pyproject.toml
│   │   │   └── src/social_intel/{main.py,fastpath/{lang.py,tickers.py,cta.py,urgency.py,minhash.py},llm/{client.py,prompts.py,schema.py},hype_scorer.py,tools.py}
│   │   ├── attribution/
│   │   │   ├── pyproject.toml
│   │   │   └── src/attribution/{main.py,loader.py,writer.py,linker.py,clustering.py,entities.py,reaction.py,latency_ks.py,tools.py,queries/*.cypher}
│   │   └── orchestrator/
│   │       ├── pyproject.toml
│   │       └── src/orchestrator/{main.py,graph.py,nodes.py,routes.py,deps.py,assess.py,clauses.py,narrator/{llm.py,template.py},bus_client.py,http.py}
│   ├── alignment_engine/
│   │   ├── pyproject.toml
│   │   └── src/alignment_engine/{main.py,series.py,xcorr.py,permutation.py,mrs.py,trigger.py,executor.py}
│   ├── evidence_engine/
│   │   ├── pyproject.toml
│   │   └── src/evidence_engine/{main.py,capture.py,ledger_service.py,dossier_builder.py,sign.py,pdf.py,bundle.py,anchor.py,templates/{dossier.html.j2,certificates/*.md.j2}}
│   ├── verifier/
│   │   ├── pyproject.toml
│   │   └── src/verifier/{core.py,cli.py}           # console_script: vigil-verify
│   ├── api/
│   │   ├── pyproject.toml
│   │   └── src/api/{main.py,auth.py,rbac.py,deps.py,ws.py,routers/{symbols.py,anomalies.py,social.py,cases.py,graph.py,dossiers.py,verify.py,ledger.py,admin.py,sim.py,accounts.py,auth.py}}
│   └── simulator/
│       ├── pyproject.toml
│       └── src/simulator/{main.py,server.py,scenarios.py,market_model.py,orderbook.py,social_model.py,ring.py,groundtruth.py,templates/{telegram_pump_en.txt,telegram_pump_hinglish.txt,organic_chatter.txt}}
├── frontend/
│   ├── package.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── playwright.config.ts
│   ├── e2e/{live.spec.ts,case.spec.ts,graph.spec.ts,verify.spec.ts}
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx                           # redirects to /live
│       │   ├── live/page.tsx
│       │   ├── cases/page.tsx
│       │   ├── cases/[caseId]/page.tsx
│       │   ├── cases/[caseId]/graph/page.tsx
│       │   ├── cases/[caseId]/timeline/page.tsx
│       │   ├── dossiers/[dossierId]/page.tsx
│       │   ├── entities/[entityId]/page.tsx
│       │   ├── verify/page.tsx
│       │   ├── simulator/page.tsx
│       │   └── admin/health/page.tsx
│       ├── components/{Heatmap.tsx,AlignedChart.tsx,AlertFeed.tsx,CaseTable.tsx,GraphCanvas.tsx,EdgeInspector.tsx,DossierView.tsx,VerifyBadge.tsx,ReviewPanel.tsx,ScenarioControl.tsx}
│       ├── lib/{api.ts,ws.ts,auth.ts,verify.ts,format.ts}
│       └── state/{useStream.ts,useGraphStore.ts}
├── scripts/
│   ├── gen_dev_keys.sh
│   ├── wait_for_stack.sh
│   ├── smoke_test.sh
│   ├── load_test.py                    # locust/aiokafka injector
│   ├── chaos_test.sh
│   └── export_schemas.py               # Pydantic → JSON Schema (CI diff check)
├── datasets/
│   └── social_labeled_v1.jsonl         # ≥500 labeled messages (generated by simulator + hand edits)
├── keys/                               # gitignored; dev keys
└── tests/
    ├── unit/{test_volume_detector.py,test_wash_cycle.py,test_hype_score.py,test_xcorr.py,test_merkle.py,test_ledger_chain.py,test_signing.py,test_noisy_or.py}
    ├── contract/test_schemas.py        # sample payloads validate; generated==committed
    ├── integration/{test_ingest_pipeline.py,test_cypher_cycles.py,test_orchestrator_resume.py,test_verify_tamper.py}
    └── e2e/test_scenarios.py           # runs scenario, asserts ground-truth metrics (AC-*)
```

---

## 11. Deployment & Local Setup

### 11.1 Prerequisites
Docker ≥ 25 with Compose v2, 8 vCPU / 16 GB RAM free, `make`, `curl`, `jq`. Optional: `uv` and `pnpm` for local non-container dev.

### 11.2 `.env.example`
```dotenv
ENV=dev
LOG_LEVEL=INFO
PUBLIC_BASE_URL=http://localhost:3000

# Kafka / Redpanda
KAFKA_BOOTSTRAP=redpanda:9092
KAFKA_ACKS=1
# Redis
REDIS_URL=redis://redis:6379/0
# Timescale / Postgres
PG_DSN=postgresql://vigil:vigil@timescale:5432/vigil
# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=vigilneo4j
# Object store
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=vigil
S3_SECRET_KEY=vigilvigil123
S3_REGION=us-east-1
# Crypto
SIGNER=file                       # file | vault
SIGNING_KEY_PATH=/keys/dev_ed25519.pem
SIGNING_KEY_ID=dev-2026-01
PSEUDONYM_PEPPER=change-me-dev-pepper-32bytes-min
TSA_URL=
# LLM (optional; system degrades gracefully if empty)
ANTHROPIC_API_KEY=
LLM_MODEL=claude-sonnet-5-5
LLM_TIMEOUT_S=2.0
LLM_MAX_CONCURRENCY=8
LLM_TRACE_STORE_TEXT=false
# Market / social inputs
MARKET_ADAPTER=websocket
MARKET_WS_URL=ws://simulator:8090/ws/market
SOCIAL_ADAPTER=synthetic_ws
SOCIAL_WS_URL=ws://simulator:8090/ws/social
INGEST_QUEUE_HIGH_WATERMARK=50000
# Agents
ALIGN_INTERVAL_S=5
ALIGN_LOOKBACK_S=3600
ORCH_MAX_CONCURRENT_CASES=8
# Auth (dev)
JWT_HS256_SECRET=dev-secret-change-me
OIDC_ISSUER=
# Frontend
NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_BASE=ws://localhost:8000/ws/v1
```

### 11.3 `docker-compose.yml` (normative)

```yaml
name: vigil
x-py: &py
  build: { context: ., dockerfile: docker/python.Dockerfile }
  env_file: .env
  restart: unless-stopped
  volumes: [ "./config:/app/config:ro", "./keys:/keys:ro" ]
  depends_on:
    redpanda: { condition: service_healthy }
    timescale: { condition: service_healthy }
    redis: { condition: service_healthy }

services:
  redpanda:
    image: redpandadata/redpanda:v24.2.7
    command: [redpanda, start, --smp, "2", --memory, 2G, --overprovisioned, --node-id, "0",
              --kafka-addr, "internal://0.0.0.0:9092,external://0.0.0.0:19092",
              --advertise-kafka-addr, "internal://redpanda:9092,external://localhost:19092"]
    ports: ["19092:19092"]
    healthcheck: { test: ["CMD-SHELL","rpk cluster health | grep -q 'Healthy:.*true'"], interval: 5s, timeout: 5s, retries: 30 }
  redpanda-init:
    image: redpandadata/redpanda:v24.2.7
    depends_on: { redpanda: { condition: service_healthy } }
    volumes: ["./infra/redpanda/create_topics.sh:/create_topics.sh:ro"]
    entrypoint: ["/bin/bash","/create_topics.sh"]
    restart: "no"
  redpanda-console:
    image: redpandadata/console:v2.7.2
    environment: { KAFKA_BROKERS: "redpanda:9092" }
    ports: ["8080:8080"]
    depends_on: [redpanda]

  redis:
    image: redis:7.4-alpine
    command: ["redis-server","--appendonly","yes","--maxmemory","1gb","--maxmemory-policy","noeviction"]
    healthcheck: { test: ["CMD","redis-cli","ping"], interval: 5s, retries: 20 }
    volumes: ["redis-data:/data"]

  timescale:
    image: timescale/timescaledb:latest-pg16
    environment: { POSTGRES_USER: vigil, POSTGRES_PASSWORD: vigil, POSTGRES_DB: vigil }
    ports: ["5432:5432"]
    volumes: ["ts-data:/var/lib/postgresql/data","./infra/postgres/init:/docker-entrypoint-initdb.d:ro"]
    command: ["postgres","-c","shared_preload_libraries=timescaledb","-c","max_connections=300","-c","synchronous_commit=off"]
    healthcheck: { test: ["CMD-SHELL","pg_isready -U vigil -d vigil"], interval: 5s, retries: 30 }

  neo4j:
    image: neo4j:5.24-community
    environment:
      NEO4J_AUTH: neo4j/vigilneo4j
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_server_memory_heap_max__size: 2G
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*"
    ports: ["7474:7474","7687:7687"]
    volumes: ["neo4j-data:/data"]
    healthcheck: { test: ["CMD-SHELL","cypher-shell -u neo4j -p vigilneo4j 'RETURN 1' || exit 1"], interval: 10s, retries: 30 }

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment: { MINIO_ROOT_USER: vigil, MINIO_ROOT_PASSWORD: vigilvigil123 }
    ports: ["9000:9000","9001:9001"]
    volumes: ["minio-data:/data"]
    healthcheck: { test: ["CMD","mc","ready","local"], interval: 5s, retries: 20 }
  minio-init:
    image: minio/mc:latest
    depends_on: { minio: { condition: service_healthy } }
    volumes: ["./infra/minio/init.sh:/init.sh:ro"]
    entrypoint: ["/bin/sh","/init.sh"]
    restart: "no"

  migrate:
    <<: *py
    command: ["sh","-c","alembic -c migrations/timescale/alembic.ini upgrade head && python -m vigil_common.neo4j_migrate"]
    depends_on: { timescale: { condition: service_healthy }, neo4j: { condition: service_healthy } }
    restart: "no"

  market_ingest:  { <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/market_ingest } },  command: ["python","-m","market_ingest.main"],  environment: { HEALTH_PORT: "8000" }, depends_on: { migrate: { condition: service_completed_successfully }, redpanda-init: { condition: service_completed_successfully } } }
  social_ingest:  { <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/social_ingest } },  command: ["python","-m","social_ingest.main"],  depends_on: { migrate: { condition: service_completed_successfully }, redpanda-init: { condition: service_completed_successfully } } }
  stream_sink:    { <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/stream_sink } },    command: ["python","-m","stream_sink.main"],    depends_on: { migrate: { condition: service_completed_successfully }, minio-init: { condition: service_completed_successfully }, redpanda-init: { condition: service_completed_successfully } } }
  quant_telemetry:{ <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/agents/quant_telemetry } }, command: ["python","-m","quant_telemetry.main"], depends_on: { migrate: { condition: service_completed_successfully }, redpanda-init: { condition: service_completed_successfully } } }
  social_intel:   { <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/agents/social_intel } },    command: ["python","-m","social_intel.main"],   depends_on: { migrate: { condition: service_completed_successfully }, redpanda-init: { condition: service_completed_successfully } } }
  alignment_engine:{ <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/alignment_engine } },   command: ["python","-m","alignment_engine.main"], depends_on: { migrate: { condition: service_completed_successfully }, redpanda-init: { condition: service_completed_successfully } } }
  attribution:    { <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/agents/attribution } },     command: ["python","-m","attribution.main"],    depends_on: { migrate: { condition: service_completed_successfully }, neo4j: { condition: service_healthy }, redpanda-init: { condition: service_completed_successfully } } }
  orchestrator:   { <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/agents/orchestrator } },    command: ["python","-m","orchestrator.main"],   depends_on: { migrate: { condition: service_completed_successfully }, neo4j: { condition: service_healthy }, redpanda-init: { condition: service_completed_successfully } } }
  evidence_engine:{ <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/evidence_engine } },        command: ["python","-m","evidence_engine.main"], depends_on: { migrate: { condition: service_completed_successfully }, minio-init: { condition: service_completed_successfully } } }
  api:            { <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/api } }, command: ["uvicorn","api.main:app","--host","0.0.0.0","--port","8000","--loop","uvloop"], ports: ["8000:8000"], depends_on: { migrate: { condition: service_completed_successfully }, neo4j: { condition: service_healthy } } }
  simulator:      { <<: *py, build: { context: ., dockerfile: docker/python.Dockerfile, args: { SERVICE_PATH: services/simulator } }, command: ["python","-m","simulator.main"], ports: ["8090:8090"], depends_on: {} }

  frontend:
    build: { context: ., dockerfile: docker/frontend.Dockerfile }
    env_file: .env
    ports: ["3000:3000"]
    depends_on: [api]

  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.108.0
    volumes: ["./infra/otel/otel-collector.yaml:/etc/otelcol-contrib/config.yaml:ro"]
  prometheus:
    image: prom/prometheus:v2.54.1
    volumes: ["./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro"]
    ports: ["9090:9090"]
  grafana:
    image: grafana/grafana:11.2.0
    ports: ["3001:3000"]
    volumes: ["./infra/grafana/provisioning:/etc/grafana/provisioning:ro","./infra/grafana/dashboards:/var/lib/grafana/dashboards:ro"]
    depends_on: [prometheus]

volumes: { redis-data: {}, ts-data: {}, neo4j-data: {}, minio-data: {} }
```
`docker/python.Dockerfile`: `python:3.12-slim`, install system libs for WeasyPrint (`libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-dejavu`), `uv sync --frozen --package <service>`; non-root user; `ENTRYPOINT` overridden by compose `command`.

### 11.4 Makefile targets
```makefile
up:            ; ./scripts/gen_dev_keys.sh && docker compose up -d --build && ./scripts/wait_for_stack.sh
down:          ; docker compose down
nuke:          ; docker compose down -v
logs:          ; docker compose logs -f --tail=200 $(S)
migrate:       ; docker compose run --rm migrate
schemas:       ; uv run python scripts/export_schemas.py
lint:          ; uv run ruff check . && uv run mypy --strict libs services
test:          ; uv run pytest tests/unit tests/contract -q --cov=services --cov-fail-under=80
test-int:      ; uv run pytest tests/integration -q          # uses testcontainers
smoke:         ; ./scripts/smoke_test.sh
scenario:      ; curl -fsS -X POST "http://localhost:8090/scenarios/$(ID)/start?speed=$(or $(SPEED),10)&seed=$(or $(SEED),42)"
load-test:     ; uv run python scripts/load_test.py --rate 5000 --duration 900
chaos:         ; ./scripts/chaos_test.sh
verify:        ; uv run vigil-verify $(BUNDLE) --pubkey keys/dev_ed25519.pub
```

### 11.5 Simulator (`services/simulator`)
- HTTP control (port 8090): `POST /scenarios/{id}/start?speed=<float>&seed=<int>`, `POST /scenarios/{id}/stop`, `GET /status`, `GET /groundtruth/{id}` (ring accounts, cycles, lag, spoofers).
- WebSocket feeds mimic external vendors: `ws://simulator:8090/ws/market` (frames: `{"kind":"trade"|"l2"|"l3","data":{…per §PRD 5.1–5.3…}}`), `ws://simulator:8090/ws/social` (frames: `SocialMessage` JSON).
- Market model: 40 symbols (30 large/mid, 10 micro/SME), per-symbol Poisson arrivals with intraday seasonality, geometric Brownian price + bid/ask microstructure; L2 snapshots every 250 ms; L3 events derived from a toy matching engine (`orderbook.py`). Accounts: 2,000 organic accounts across 12 brokers with realistic device/IP reuse (≤ 2 accounts per device, ≤ 5 per ASN).
- Social model: 25 channels (organic chatter templates incl. Hinglish) and 3 pump channels per scenario; message templates parameterized with `{ticker}`, `{target}`, `{time}`; cross-posting with jitter.
- Scenario YAML schema (`config/scenarios/*.yaml`):
```yaml
id: pump_dump_ring_01
duration_s: 1800
target: { symbol: ZENITHSME, tier: micro, base_price: 40.0, base_rate_tps: 0.4 }
social:
  channels: 3
  t0_s: 300
  burst: { msgs_per_min: 90, duration_s: 600, cta_mix: { BUY_CALL: 0.45, HOLD_PUMP: 0.2, COORDINATION_TIMING: 0.15, TARGET_PRICE: 0.1, NEUTRAL: 0.1 }, near_dup_ratio: 0.5, languages: [en, hinglish] }
ring:
  accounts: 20
  brokers: 3
  shared_devices: 5
  shared_asn: 1
  reaction_lag_s: { mean: 150, sd: 20 }
  buy_volume_share: 0.45
  wash_cycles: { count: 6, lengths: [2,3,4], qty: 1000 }
  dump_start_s: 1140
price_effect: { pump_pct: 38.0, dump_pct: -30.0 }
ground_truth_out: true
```
- All randomness from `numpy.random.Generator(PCG64(seed))`; same seed ⇒ byte-identical event stream (NFR-INT-02).
- Ground-truth labels are never written into agent-visible fields (the `scenario_label`/`is_synthetic` fields are retained for evaluation only and stripped by `market_ingest` before publishing to `*.norm` unless `KEEP_SCENARIO_LABELS=true` for tests).

### 11.6 Smoke test (`scripts/smoke_test.sh`, `make smoke`)
```bash
#!/usr/bin/env bash
set -euo pipefail
API=${API:-http://localhost:8000/api/v1}; SIM=${SIM:-http://localhost:8090}
echo "[1/8] health";        for s in healthz readyz; do curl -fsS "http://localhost:8000/$s" >/dev/null; done
echo "[2/8] token";         TOKEN=$(curl -fsS -X POST "$API/auth/dev-token" -H 'content-type: application/json' -d '{"sub":"smoke-c","role":"compliance_officer"}' | jq -r .token)
H=(-H "authorization: Bearer $TOKEN")
echo "[3/8] baseline 60s";  curl -fsS -X POST "$SIM/scenarios/baseline_01/start?speed=20&seed=1" >/dev/null; sleep 60
N=$(curl -fsS "${H[@]}" "$API/cases?limit=1" | jq '.items|length'); [ "$N" -eq 0 ] || { echo "FAIL: case opened on baseline"; exit 1; }
curl -fsS -X POST "$SIM/scenarios/baseline_01/stop" >/dev/null
echo "[4/8] pump scenario"; curl -fsS -X POST "$SIM/scenarios/pump_dump_ring_01/start?speed=10&seed=42" >/dev/null
echo "[5/8] wait for case (≤300s)"
for i in $(seq 1 60); do
  CID=$(curl -fsS "${H[@]}" "$API/cases?symbol=ZENITHSME&status=PENDING_REVIEW" | jq -r '.items[0].case_id // empty')
  [ -n "$CID" ] && break; sleep 5
done; [ -n "${CID:-}" ] || { echo "FAIL: no case reached PENDING_REVIEW"; exit 1; }
echo "[6/8] graph + ring";  curl -fsS "${H[@]}" "$API/cases/$CID/graph" | jq -e '.nodes|length>=15' >/dev/null
DID=$(curl -fsS "${H[@]}" "$API/cases/$CID/dossiers" | jq -r '.items[0].dossier_id')
curl -fsS "${H[@]}" "$API/dossiers/$DID" | jq -e '.attribution.rings[0].ring_score>=0.8 and .signature.alg=="Ed25519"' >/dev/null
echo "[7/8] verify";        curl -fsS "${H[@]}" "$API/dossiers/$DID/verify" | jq -e '.valid==true' >/dev/null
echo "[8/8] approve+publish"
curl -fsS -X POST "${H[@]}" -H 'content-type: application/json' "$API/cases/$CID/review" -d '{"status":"APPROVED","comment":"smoke"}' >/dev/null
for i in $(seq 1 24); do ST=$(curl -fsS "${H[@]}" "$API/cases/$CID" | jq -r .status); [ "$ST" = PUBLISHED ] && break; sleep 5; done
[ "$ST" = PUBLISHED ] || { echo "FAIL: not published"; exit 1; }
LATEST=$(curl -fsS "${H[@]}" "$API/cases/$CID/dossiers" | jq -r '.items[0].dossier_id')
curl -fsS "${H[@]}" "$API/dossiers/$LATEST/bundle" -o /tmp/vigil_bundle.zip
uv run vigil-verify /tmp/vigil_bundle.zip --pubkey keys/dev_ed25519.pub
# tamper test
cp /tmp/vigil_bundle.zip /tmp/tampered.zip && printf '\x00' | dd of=/tmp/tampered.zip bs=1 seek=200 count=1 conv=notrunc 2>/dev/null
! uv run vigil-verify /tmp/tampered.zip --pubkey keys/dev_ed25519.pub || { echo "FAIL: tamper not detected"; exit 1; }
echo "SMOKE OK"
```

### 11.7 Quick start
```bash
cp .env.example .env            # optionally set ANTHROPIC_API_KEY (system works without it)
make up                         # builds & starts everything; waits for readiness
open http://localhost:3000      # dashboard      (API docs: http://localhost:8000/docs)
make scenario ID=pump_dump_ring_01 SPEED=10 SEED=42
make smoke                      # full automated end-to-end acceptance
```
Service URLs: Dashboard `:3000`, API `:8000`, Simulator `:8090`, Redpanda Console `:8080`, Neo4j Browser `:7474`, MinIO Console `:9001`, Prometheus `:9090`, Grafana `:3001`.

### 11.8 Production topology notes (non-binding for MVP)
Kubernetes with one Deployment per service; HPA on Kafka consumer lag (KEDA); Redpanda/Kafka ≥ 3 brokers RF=3, partitions ≥ 32 for `market.*`; Timescale via managed HA / Patroni; Neo4j causal cluster (Enterprise) or AuraDB; MinIO → S3 with Object Lock (compliance mode) for `vigil-evidence`, `vigil-dossiers`, `vigil-anchors`; signing via Vault Transit/HSM; network policies isolating the evidence engine; mTLS between services.

---

## 12. Configuration Reference (`config/detectors.yaml` excerpt — normative shape)

```yaml
version: "1.0.0"
tiers:
  micro: { volume_spike: { z_thr: 4.0, k: 3 }, price_jump: { sigma_thr: 5.0 } }
  mid:   { volume_spike: { z_thr: 5.0, k: 3 }, price_jump: { sigma_thr: 5.0 } }
  large: { volume_spike: { z_thr: 6.0, k: 4 }, price_jump: { sigma_thr: 6.0 } }
spread_depth: { spread_mult: 3.0, imbalance_thr: 0.7, imbalance_hold_s: 10, top_levels: 5 }
spoofing:     { window_ms: 2000, min_orders: 5, cancel_ratio: 0.9, qty_mult: 5, exec_ms: 1000 }
wash_cycle:   { cycle_window_s: 900, qty_tol: 0.05, price_tol: 0.005, max_len: 4 }
sync_orders:  { bin_ms: 500, min_accounts: 3, min_bins: 3, window_s: 600, p_thr: 0.01 }
alignment:    { lags_s: [-120, 1800], block_s: 60, shuffles: 500, peak_thr: 0.5, p_thr: 0.01, max_lag_s: 900 }
hype:         { burst_score: 70, burst_hold_s: 30, window_s: 60, step_s: 5, min_msgs: 5 }
case:         { overlap_merge_ratio: 0.5, watchlist_cooldown_min: 60, min_conf_proceed: 0.40, min_conf_no_loop: 0.60, max_widen: 2 }
```
`config_hash = sha256(JCS(parsed yaml))` is embedded in every `AnomalyEvent`. Hot reload: watch file mtime every 5 s; on change validate with Pydantic, swap atomically, log `CONFIG_RELOADED`.

---

## 13. Testing & CI

- **Unit:** detectors with synthetic series (known z-scores), Merkle/ledger/signing round-trips, noisy-OR math, hype formula, xcorr on injected lag (±2 s tolerance).
- **Contract:** every schema example in `PRD.md §5` validates; Pydantic-generated schema equals committed schema (`scripts/export_schemas.py --check`).
- **Integration (testcontainers):** ingest pipeline with malformed/duplicate/gapped events; Cypher cycle query on a seeded graph (expects exact cycles); orchestrator crash-resume; verifier tamper matrix (flip a byte in dossier, evidence, ledger proof, signature).
- **E2E (`tests/e2e/test_scenarios.py`):** runs each scenario at `speed=20`, fetches simulator ground truth, and asserts the AC thresholds in PRD §6.2 (precision/recall for rings, cycles, spoofers; alignment lag error ≤ 30 s; zero cases on baseline across seeds 1–5).
- **Frontend:** Playwright flows for `/live`, case → graph → dossier → verify.
- **CI (`.github/workflows/ci.yml`):** `ruff`, `mypy --strict`, unit+contract, build images, `docker compose up` + `make smoke` (nightly and on `main`), `trivy` scan, `pip-audit`, `pnpm audit`.

---

## 14. Implementation Order for the Code Generator

1. **Scaffold:** repo tree (§10), `pyproject` workspace, `vigil_common` (config, logging, ids, hashing, canonical, topics, models, schema export), Dockerfiles, compose, `.env.example`, Makefile, infra scripts.
2. **Migrations:** Alembic `0001–0004` (SQL in §3.3), Neo4j constraints (§6.3), `vigil_common.neo4j_migrate`.
3. **Simulator** (baseline + pump_dump_ring first) — needed to test everything else.
4. **market_ingest**, **social_ingest**, **stream_sink** → verify AC-ING-*.
5. **quant_telemetry** detectors → AC-QTA-*.
6. **social_intel** fast path → hype scorer → LLM refinement path → AC-SOC-*.
7. **alignment_engine** → AC-ALN-*.
8. **attribution** (loader/writer → linker → clustering → entities) with Cypher §6.4 → AC-GRA-*.
9. **evidence_engine** + **verifier** (ledger, Merkle, signing, PDF, bundle) → AC-DOS-*.
10. **orchestrator** (graph §5.5, nodes, routes, narrator LLM + template, assess/clauses) → AC-ORC-*.
11. **api** (routers §8, auth/RBAC, WS) and **frontend** routes (§10) → AC-UI-*.
12. **Hardening:** metrics dashboards, load/chaos scripts, CI, docs → AC-NFR-*; run `make smoke` until green.

**Definition of done for each step:** code + unit tests + contract tests pass, `ruff` and `mypy --strict` clean, relevant AC from `PRD.md §6.2` demonstrably satisfied via the simulator scenarios.
