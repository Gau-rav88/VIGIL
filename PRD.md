# PRD — Project VIGIL
### Autonomous Multi-Agent Forensic Intelligence Platform for Capital-Market Manipulation

| Field | Value |
|---|---|
| Document version | 1.0.0 |
| Status | Approved for implementation |
| Audience | Autonomous code-generation engine; engineering; regulatory product owners |
| Companion document | `ARCHITECTURE.md` (the technical source of truth for implementation) |
| Codename | VIGIL (Versatile Intelligence for Gathering Illicit-trading Linkages) |

> **Conventions used in this document.** `MUST`, `SHOULD`, `MAY` follow RFC 2119. Every requirement has a stable ID (`FR-*`, `NFR-*`, `AC-*`). All timestamps are RFC 3339 UTC with nanosecond precision where available. All monetary values are decimal strings or integers in minor units; never binary floats in persisted evidence.

---

## 1. Executive Summary & Scope

### 1.1 Mission statement
Compress the manipulation-investigation lifecycle from **months to minutes** by fusing high-frequency order-book telemetry with public social/OSINT signals, automatically unmasking coordinated trading syndicates, and compiling cryptographically signed, court-ready regulatory dossiers, **with a human investigator always in the decision loop**.

### 1.2 Problem recap
Pump-and-dump cartels, circular wash trading and coordinated liquidity squeezing span (a) social channels (Telegram, Discord, Reddit, X, StockTwits, finance forums) and (b) synchronized micro-cap orders across dispersed broker accounts, shell entities and synthetic identities. Surveillance systems keep these two worlds in silos, so forensic auditors manually correlate petabytes of ticks and chat logs.

### 1.3 Primary stakeholders

| Stakeholder | Interest |
|---|---|
| Market regulators (SEBI, SEC, equivalents) | Court-admissible evidence, enforcement throughput |
| Exchange surveillance desks (NSE, BSE, NASDAQ, NYSE) | Real-time alerts, reduced false positives |
| Regulatory compliance officers | Case approval, audit trail, clause citation |
| Forensic investigators | Explorable evidence, graph tooling, defensible attribution |
| Legal/prosecution counsel | Evidence integrity, chain of custody |
| Platform operators (SRE/DevOps) | Reliability, observability |

### 1.4 Core deliverables (in scope for MVP)
1. Real-time ingestion of L2/L3 order-book data and trade feeds (real regulator-privileged feeds via adapter; synthetic feed for MVP).
2. Social/OSINT stream ingestion, semantic parsing, ticker extraction, and hype-burst scoring.
3. Cross-modal temporal alignment of social triggers and market anomalies.
4. Identity attribution, graph clustering, and syndicate-ring detection (wash cycles, synchronized volume loops, shared-fingerprint clusters).
5. Cryptographically signed dossier generation (PDF + JSON) with independent verification.
6. Investigator web dashboard (live monitor, case workbench, graph explorer, dossier viewer, verifier).
7. Deterministic simulator/mock-data generators and an automated smoke/acceptance suite.

### 1.5 Out of scope (MVP)
- Order-routing, trading, or any action against market participants (VIGIL is read-only analytics).
- Breaking encryption or joining private/invite-only channels without lawful authority. Ingestion is limited to **public channels** and **lawful-access feeds** supplied by the regulator (field `channel_visibility`).
- Automated accusations or enforcement. All outputs are *investigative leads with confidence scores*; publication requires human approval (FR-DOS-07).
- Production exchange connectivity certification (adapter interfaces are defined; vendor-specific adapters are post-MVP).
- Native mobile apps.

### 1.6 Ethical, legal & safety guardrails (binding requirements)
- **G-1 Human-in-the-loop:** No dossier reaches status `PUBLISHED` without an authenticated reviewer approval event.
- **G-2 Probabilistic attribution:** Identity links are stored with `confidence ∈ [0,1]`, `method`, and `evidence_refs`. UI and dossiers MUST display confidence and limitations; links with confidence < 0.60 MUST be labelled `INFERRED-LOW` and excluded from the dossier's "attribution findings" (listed under "leads").
- **G-3 Pseudonymization:** Account, handle, IP, device and KYC identifiers are stored as keyed HMAC-SHA-256 pseudonyms. Re-identification requires a privileged `reveal` API call that is itself audit-logged.
- **G-4 Auditability:** Every agent decision, LLM call (prompt hash + response hash), and human action is logged in the append-only evidence ledger.
- **G-5 Data minimization:** Social text is retained for a configurable period (default 180 days) unless attached to an open case (legal hold).

---

## 2. User Personas & Workflows

### 2.1 Persona A — Forensic Investigator ("Priya Nair", Senior Surveillance Analyst)
**Goals:** Triage alerts quickly, understand *why* the system flagged a case, explore the account/entity graph, challenge system conclusions, and export defensible evidence.
**Pain points today:** Weeks stitching chat exports to tick files; no reproducibility; alert fatigue.

**End-to-end journey (system-supported):**

| Step | Investigator action | System behavior | Requirement refs |
|---|---|---|---|
| 1 | Opens **Live Monitor** (`/live`) and sees a ranked ticker heatmap by *Manipulation Risk Score (MRS)* | Streams hype scores, volume z-scores, spread, depth imbalance via WebSocket | FR-UI-01 |
| 2 | Receives an alert: *"XYZ-SME: hype burst @ 10:02:11Z, volume anomaly @ 10:04:40Z, lag 149 s"* | Orchestrator opens a `Case` automatically after cross-modal alignment | FR-ALN-03, FR-ORC-01 |
| 3 | Opens **Case Workbench** (`/cases/{id}`): overlay chart of hype score vs. traded volume vs. price, with social trigger markers | Serves aligned timeline from TimescaleDB | FR-UI-03 |
| 4 | Opens **Graph Explorer** (`/cases/{id}/graph`): sees 14 accounts in 2 clusters, a 4-hop wash cycle highlighted, 9 accounts sharing a device fingerprint | Runs Cypher/GDS queries, returns Cytoscape-compatible JSON | FR-GRA-01..06, FR-UI-04 |
| 5 | Clicks an edge to inspect underlying trades and fingerprints; flags a link as *false positive* | Records feedback; link confidence recomputed; ledger entry written | FR-GRA-07 |
| 6 | Requests **Re-run attribution with wider window (±2 h)** | Orchestrator re-enters the ATTRIBUTE state with new parameters | FR-ORC-04 |
| 7 | Reviews auto-drafted narrative and clause mapping, edits text where wrong | Dossier draft is versioned; edits are diffed and ledgered | FR-DOS-04, FR-DOS-06 |
| 8 | Submits case for compliance review | Case state → `PENDING_REVIEW` | FR-ORC-06 |

### 2.2 Persona B — Regulatory Compliance Officer ("Arjun Mehta", Enforcement Department)
**Goals:** Decide whether evidence meets the threshold for show-cause/enforcement; ensure admissibility; maintain chain of custody.

**End-to-end journey:**

| Step | Officer action | System behavior | Requirement refs |
|---|---|---|---|
| 1 | Opens **Review Queue** (`/cases?status=PENDING_REVIEW`) | Lists cases with MRS, confidence, completeness score | FR-UI-02 |
| 2 | Opens dossier viewer (`/dossiers/{id}`) | Renders signed dossier; shows "Signature VALID / Ledger VALID" badge from live verification | FR-DOS-08 |
| 3 | Reads timeline aligning social triggers to illicit volume and the list of cited clauses | Displays clause registry entries with rationale | FR-DOS-03 |
| 4 | Approves, rejects, or requests rework with comments | Writes `human_review` object, re-signs dossier (new version, `supersedes` pointer) | FR-DOS-07 |
| 5 | Exports PDF + JSON + detached signature + evidence bundle (ZIP) | Streams export; includes certificate-of-integrity page (BSA 2023 §63 / FRE 902(13)–(14)-style template, jurisdiction-configurable, **legal review required**) | FR-DOS-05 |
| 6 | Hands the bundle to counsel; counsel runs the independent **Verifier** (`/verify` or `vigil-verify` CLI) offline | Verifier recomputes hashes, Merkle root, ledger chain, Ed25519 signature | FR-DOS-09 |

### 2.3 Persona C — Platform SRE (secondary)
Monitors ingestion lag, consumer-group lag, agent failure rates, and key-rotation status via `/admin/health` and Prometheus/Grafana.

---

## 3. Functional Requirements

### 3.1 Market Telemetry Ingestion (FR-MKT)

| ID | Requirement |
|---|---|
| FR-MKT-01 | The system MUST ingest **trade ticks**, **L2 snapshots/deltas (≥10 levels)**, and **L3 order events** (NEW/MODIFY/CANCEL/TRADE) conforming to the schemas in §5.1–§5.3. |
| FR-MKT-02 | Ingestion MUST support three adapters behind one interface `MarketFeedAdapter`: (a) `SyntheticFeedAdapter` (MVP default, driven by the simulator), (b) `WebSocketFeedAdapter` (generic JSON/WS), (c) `FileReplayAdapter` (NDJSON/Parquet replay at configurable speed). |
| FR-MKT-03 | Each event MUST be validated against its JSON Schema; invalid events MUST go to the DLQ topic `dlq.market` with the validation error, never dropped silently. |
| FR-MKT-04 | Events MUST be partitioned by `symbol` so per-symbol ordering is preserved. A per-symbol monotonic `seq` MUST be validated; gaps MUST emit a `SEQ_GAP` health event. |
| FR-MKT-05 | Ingestion MUST stamp `ts_ingest` (monotonic-corrected wall clock) and compute `ingest_latency_us`. |
| FR-MKT-06 | Ingestion MUST be idempotent: duplicate `event_id` within a 10-minute window MUST be discarded and counted. |
| FR-MKT-07 | Raw events MUST be persisted to object storage (`vigil-raw/market/YYYY/MM/DD/HH/…ndjson.zst`) with per-file SHA-256 recorded in the evidence ledger (hourly rollup). |
| FR-MKT-08 | Normalized ticks and L2 aggregates (1 s bars, depth metrics) MUST be written to TimescaleDB hypertables. |

### 3.2 Quantitative Telemetry Agent (FR-QTA)

| ID | Requirement |
|---|---|
| FR-QTA-01 | **Volume anomaly:** compute per-symbol rolling robust z-score (median/MAD, 30-min baseline sampled in 1-s bars, with time-of-day seasonality factor). Emit `VOLUME_SPIKE` when `z ≥ 4.0` for ≥ 3 consecutive 5-s windows. |
| FR-QTA-02 | **Spread/depth anomaly:** emit `SPREAD_WIDENING` when relative spread exceeds 3× its rolling median; emit `DEPTH_IMBALANCE` when `|(Σbid_qty − Σask_qty)/(Σbid_qty + Σask_qty)| ≥ 0.7` over top-5 levels for ≥ 10 s. |
| FR-QTA-03 | **Spoofing/layering:** from L3 events, flag accounts whose cancel-to-new ratio within a 2-s window ≥ 0.9 on ≥ 5 orders totalling ≥ 5× the median order size, followed by an opposite-side execution within 1 s. Emit `SPOOFING_LAYERING`. |
| FR-QTA-04 | **Wash/circular trade detection (market level):** for each symbol, detect *round-trip sequences* where shares return to the originating account or beneficial-owner group within a configurable window (default 15 min) with quantity tolerance ≤ 5 % and price deviation ≤ 0.5 %. Emit `WASH_CYCLE` with the participating account pseudonyms. Graph-level confirmation is performed by the Attribution Agent (FR-GRA). |
| FR-QTA-05 | **Synchronized orders:** detect ≥ 3 distinct accounts placing same-side orders on the same symbol within a 500 ms window, repeated ≥ 3 times in 10 min, with significance p < 0.01 versus a Poisson null. Emit `SYNCHRONIZED_ORDERS`. |
| FR-QTA-06 | **Price impact:** emit `PRICE_JUMP` when 1-min log return exceeds 5 robust σ. |
| FR-QTA-07 | Each anomaly MUST include `score ∈ [0,1]`, `severity`, a metrics object, and `evidence_refs` (trade IDs / order IDs / L2 snapshot seqs) sufficient to reproduce the finding. |
| FR-QTA-08 | Detector parameters MUST be configurable per symbol-tier (large-cap, mid-cap, micro/SME) via `config/detectors.yaml`, hot-reloadable. |

### 3.3 OSINT / Social Ingestion & Semantic Parsing (FR-SOC)

| ID | Requirement |
|---|---|
| FR-SOC-01 | The system MUST ingest messages from `telegram`, `discord`, `reddit`, `x`, `stocktwits`, `forum` via pluggable `SocialSourceAdapter`s. MVP ships `SyntheticTelegramAdapter` plus a `TelegramPublicChannelAdapter` (Telethon, public channels only, disabled by default) and `FileReplayAdapter`. |
| FR-SOC-02 | Messages MUST conform to §5.4 and be deduplicated by `(platform, channel_id, message_id)`. |
| FR-SOC-03 | **Ticker/entity extraction:** extract cashtags (`$XYZ`), bare tickers, company names and aliases (alias dictionary `config/ticker_aliases.yaml`), including Hinglish/Indic transliterations. Confidence per mention. |
| FR-SOC-04 | **Call-to-action classification** into `BUY_CALL`, `HOLD_PUMP`, `TARGET_PRICE`, `EXIT_SIGNAL`, `COORDINATION_TIMING` (e.g., "everyone buy at 10:15 sharp"), `NEUTRAL`. Primary: LLM structured-output classifier. Mandatory deterministic fallback: rules + multilingual embedding nearest-centroid classifier. |
| FR-SOC-05 | **Coordination signatures:** near-duplicate detection (MinHash-LSH, Jaccard ≥ 0.8) across channels within 5 min; forwarded-message cascades; synchronized posting by distinct handles. Output `near_dup_cluster_id`. |
| FR-SOC-06 | **Hype-burst scoring:** compute per-ticker `hype_score ∈ [0,100]` every 5 s from message-rate EWMA z-score, unique-author growth, CTA density, near-duplicate ratio, urgency lexicon and cross-channel spread (formula in `ARCHITECTURE.md` §7.2). Emit `HYPE_BURST` at `hype_score ≥ 70` sustained ≥ 30 s. |
| FR-SOC-07 | Each social signal MUST retain a link to the raw message hash (`raw_sha256`) for evidence. |
| FR-SOC-08 | Only `channel_visibility ∈ {public, lawful_access}` are accepted; others are rejected to `dlq.social` with reason `VISIBILITY_NOT_PERMITTED`. |

### 3.4 Cross-Modal Temporal Alignment (FR-ALN)

| ID | Requirement |
|---|---|
| FR-ALN-01 | For each ticker, maintain aligned 1-s series of `hype_score`, `volume_z`, `abs_return`, `spread_rel`. |
| FR-ALN-02 | Compute lagged normalized cross-correlation over lags −120 s … +1800 s; report `best_lag_s`, `xcorr_peak`, and a permutation-test p-value (≥ 500 shuffles, circular block shuffle). |
| FR-ALN-03 | Emit `CROSS_MODAL_ALIGNMENT` when `xcorr_peak ≥ 0.5`, `p < 0.01`, and `0 ≤ best_lag_s ≤ 900` (social leads market), or when a `HYPE_BURST` precedes a `VOLUME_SPIKE`/`PRICE_JUMP` on the same ticker within 15 min. This event is the **case-opening trigger**. |
| FR-ALN-04 | Produce a **Manipulation Risk Score (MRS ∈ [0,100])** per ticker per minute (formula in `ARCHITECTURE.md` §7.4). |
| FR-ALN-05 | Maintain an *event-time* join with a 30-s watermark so late social messages still align. |

### 3.5 Identity Attribution, Graph Clustering & Syndicate Detection (FR-GRA)

| ID | Requirement |
|---|---|
| FR-GRA-01 | Maintain a property graph (Neo4j) with nodes `Trader`, `Broker`, `Ticker`, `Channel`, `Device`, `Handle`, `NetworkFingerprint`, `Entity`, `Case` and edges per `ARCHITECTURE.md` §6. |
| FR-GRA-02 | **Fingerprint clustering:** link `Trader` nodes sharing `Device`, `NetworkFingerprint` (ip_hash/ASN/API-client), KYC-derived attributes (phone/bank/address hashes), or near-identical latency signatures (Kolmogorov–Smirnov p > 0.2 on order-to-ack latency distributions with ≥ 50 samples each). |
| FR-GRA-03 | **Broker-pathway analysis:** flag accounts that concentrate ≥ 80 % of their flow through the same `(broker_id, gateway_id)` as ≥ 2 other accounts in the same case. |
| FR-GRA-04 | **Circular-trading rings:** detect directed cycles of length 2–6 over `TRADED_WITH` edges within a window with net-position change ≈ 0 for each participant (query in `ARCHITECTURE.md` §6.4). |
| FR-GRA-05 | **Coordinated volume loops:** find communities (Louvain/WCC via Neo4j GDS) over `SYNCHRONIZED_WITH` + `SHARES_FINGERPRINT` edges whose combined volume ≥ 25 % of symbol volume in the case window. |
| FR-GRA-06 | **Social-to-trader linking:** compute `REACTED_TO` edges using reaction-latency analysis (trader's first aggressive order after a CTA message; null model = latency distribution to random timestamps). Direct handle→trader links (`LINKED_TO`) are created **only** from lawful-access data (e.g., matched phone-hash) and carry `method`. |
| FR-GRA-07 | Investigator feedback (confirm/reject link) MUST update edge `confidence` and be ledgered. |
| FR-GRA-08 | Resolve clusters to `Entity` nodes (probable common beneficial control) with `ring_score ∈ [0,1]` (formula in `ARCHITECTURE.md` §7.5). |
| FR-GRA-09 | Expose `GET /api/v1/cases/{id}/graph` returning Cytoscape.js elements JSON. |

### 3.6 Orchestration (FR-ORC)

| ID | Requirement |
|---|---|
| FR-ORC-01 | A LangGraph-based Orchestrator Agent MUST open a Case on `CROSS_MODAL_ALIGNMENT` and drive it through the state machine in `ARCHITECTURE.md` §5. |
| FR-ORC-02 | Case state MUST be checkpointed to PostgreSQL after every node; a crash MUST resume from the last checkpoint with no duplicate side effects (idempotency keys). |
| FR-ORC-03 | Orchestrator MUST enforce per-state timeouts and fallback loops (§5.4). |
| FR-ORC-04 | Investigators MUST be able to inject directives (`WIDEN_WINDOW`, `EXCLUDE_ACCOUNT`, `FORCE_REATTRIBUTION`) via API; the Orchestrator re-enters the relevant state. |
| FR-ORC-05 | All inter-agent messages MUST be typed (Pydantic), versioned, and logged. |
| FR-ORC-06 | State transitions to `PENDING_REVIEW` and `PUBLISHED` MUST be gated per G-1. |
| FR-ORC-07 | Duplicate/overlapping cases (same ticker, overlapping window) MUST be merged, not re-opened. |

### 3.7 Dossier & Evidence Generation (FR-DOS)

| ID | Requirement |
|---|---|
| FR-DOS-01 | Generate a dossier conforming to §5.6, containing: executive summary, chronological timeline (social triggers ↔ market events), market evidence, social evidence, attribution findings with confidence, violated regulatory clauses, limitations, evidence manifest. |
| FR-DOS-02 | Every factual statement in the narrative MUST reference ≥ 1 `evidence_id`. A validator MUST reject drafts containing uncited claims (regex + structured check). |
| FR-DOS-03 | **Clause registry:** `config/regulatory_clauses.yaml` maps finding types to clauses in SEBI (PFUTP Regulations, 2003 — Reg. 3 and Reg. 4(2); SEBI Act 1992 s.12A, s.15HA; SCRA) and SEC (Exchange Act §9(a)(1), §9(a)(2), §10(b), Rule 10b-5) regimes. Clause text and mapping MUST be flagged `legal_review_required: true` and are advisory. |
| FR-DOS-04 | LLM-assisted narrative drafting MUST use a constrained, schema-validated structured output; if validation fails after 2 retries, a deterministic template renderer is used. |
| FR-DOS-05 | Export: (a) canonical JSON (RFC 8785 JCS), (b) PDF (human-readable, with embedded manifest hash and QR code to verify), (c) detached signature `.sig`, (d) evidence bundle ZIP. |
| FR-DOS-06 | Dossiers are **versioned and immutable**; edits produce a new version with `supersedes`. |
| FR-DOS-07 | A reviewer approval (`APPROVED`/`REJECTED`/`REWORK`) with identity, timestamp and comment MUST be recorded before publication; approval triggers a final re-sign. |
| FR-DOS-08 | Dossier signing: SHA-256 digest of JCS-canonicalized dossier (excluding `signature`), Ed25519 signature, `key_id` reference, optional RFC 3161 timestamp token. |
| FR-DOS-09 | Evidence ledger: append-only hash-chained table; manifest Merkle root; independent verifier (CLI + `/api/v1/verify`) that works offline given the bundle and public key. |
| FR-DOS-10 | Key management: dev uses file-based keys; prod uses KMS/HSM via `Signer` interface; key rotation supported without invalidating prior signatures (`key_id` + public-key registry). |

### 3.8 API & Dashboard (FR-API / FR-UI)

| ID | Requirement |
|---|---|
| FR-API-01 | REST API under `/api/v1` (OpenAPI 3.1 auto-published at `/api/v1/openapi.json`), WebSocket at `/ws/v1/stream`. Full endpoint list in `ARCHITECTURE.md` §8. |
| FR-API-02 | AuthN via OIDC JWT (dev: local HS256 issuer); RBAC roles `investigator`, `compliance_officer`, `admin`, `auditor_readonly`. |
| FR-API-03 | All mutating calls write to the audit log/ledger. |
| FR-UI-01 | `/live`: ticker heatmap by MRS, live hype/volume charts, alert feed. |
| FR-UI-02 | `/cases`: filterable case table (status, ticker, MRS, confidence, age). |
| FR-UI-03 | `/cases/[caseId]`: aligned multi-axis timeline (Recharts), anomaly list, evidence drawer. |
| FR-UI-04 | `/cases/[caseId]/graph`: Cytoscape.js explorer with layout switcher, cycle highlight, cluster coloring, edge inspector, confirm/reject controls. |
| FR-UI-05 | `/dossiers/[dossierId]`: rendered dossier, verification badge, export buttons. |
| FR-UI-06 | `/verify`: drag-and-drop bundle verifier (client-side WebCrypto Ed25519 where supported, else server). |
| FR-UI-07 | `/simulator`: launch/stop synthetic scenarios (dev/demo mode only). |
| FR-UI-08 | `/admin/health`: service health, consumer lag, p50/p95/p99 latency. |

---

## 4. Non-Functional Requirements

### 4.1 Performance & latency

| ID | Requirement | Measurement |
|---|---|---|
| NFR-PERF-01 | **p99 ingestion processing latency < 200 ms**, defined as `ts_normalized_published − ts_received_by_ingestor` per event, sustained at the target load. | Prometheus histogram `vigil_ingest_latency_seconds{stream}` |
| NFR-PERF-02 | MVP sustained throughput ≥ **5,000 market events/s** and ≥ **500 social msgs/s** on the reference Docker Compose environment (8 vCPU / 16 GB). Production design target ≥ 100,000 events/s via partition scale-out (symbol-hash partitions, ≥ 32). | Load test `make load-test` |
| NFR-PERF-03 | Anomaly detection latency (event time → anomaly published) p95 < 2 s for QTA, p95 < 10 s for hype scoring (excluding LLM calls, which are asynchronous enrichment). | `vigil_detect_latency_seconds` |
| NFR-PERF-04 | Case-open-to-draft-dossier p95 < 5 minutes for cases with ≤ 50 accounts and ≤ 1 h window. | `vigil_case_duration_seconds` |
| NFR-PERF-05 | Graph explorer API p95 < 800 ms for ≤ 500 nodes / 5,000 edges. | API histogram |
| NFR-PERF-06 | Dashboard time-to-first-chart < 2.5 s on broadband. | Lighthouse in CI |

### 4.2 Availability & resilience
- **NFR-HA-01:** Control plane + ingestion availability target 99.9 % (production topology: ≥ 3 Kafka brokers RF=3, Timescale streaming replica with automatic failover, Neo4j causal cluster ≥ 3 cores, ≥ 2 replicas per stateless service).
- **NFR-HA-02:** RPO ≤ 5 s (stream-persisted), RTO ≤ 15 min.
- **NFR-HA-03:** At-least-once delivery end-to-end with idempotent consumers (effectively-once semantics for persisted effects).
- **NFR-HA-04:** Backpressure: consumers MUST pause/resume on lag thresholds; ingestion MUST shed *only* L2 deltas (never trades or L3 events) under overload, and MUST emit `OVERLOAD_SHED` counters.
- **NFR-HA-05:** Graceful degradation matrix (see `ARCHITECTURE.md` §5.4): LLM outage → deterministic fallbacks; Neo4j outage → buffer graph updates in `graph.updates` topic (retention 7 d).

### 4.3 Cryptographic immutability & data integrity
- **NFR-SEC-01:** All evidence artifacts hashed with **SHA-256**; hashes recorded in the hash-chained `evidence_ledger` (`entry_hash = SHA256(prev_entry_hash ‖ evidence_sha256 ‖ ts ‖ type ‖ actor)`).
- **NFR-SEC-02:** Ledger table is append-only enforced by DB triggers (`UPDATE`/`DELETE`/`TRUNCATE` raise exceptions) and periodic external anchoring (daily Merkle root written to object store with object-lock and, optionally, an RFC 3161 TSA).
- **NFR-SEC-03:** Dossiers signed with **Ed25519**; canonicalization via **RFC 8785 (JCS)** to guarantee byte-stable hashing.
- **NFR-SEC-04:** TLS 1.3 in transit (prod); AES-256 at rest (volume/object-store encryption); secrets via env/Vault, never in the repo.
- **NFR-SEC-05:** Pseudonymization via HMAC-SHA-256 with a rotating *pepper* held in KMS; re-identification endpoint requires `compliance_officer` role and writes an audit entry.
- **NFR-SEC-06:** OWASP ASVS L2 controls; dependency and container scanning in CI.
- **NFR-INT-01:** Zero tolerance for silent data loss: every discarded/rejected event is counted and routed to a DLQ with reason.
- **NFR-INT-02:** Reproducibility: given the same raw inputs, detector versions and config hash, the system MUST produce identical anomaly events (deterministic seeds; versions recorded in each event).

### 4.4 Observability
OpenTelemetry traces across services (trace id propagated in Kafka headers), Prometheus metrics, structured JSON logs with `case_id`, `symbol`, `agent`, `trace_id`.

### 4.5 Maintainability & quality
Python 3.12, strict typing (`mypy --strict` for `libs/` and `services/`), `ruff`, ≥ 80 % unit-test coverage on detectors, contract tests on every schema, semantic versioning on schemas (`schema_version`).

### 4.6 Compliance & localization
Time zone handling: store UTC; display in exchange-local time (IST for NSE/BSE, ET for US). Support Indic text (UTF-8, NFKC normalization, transliteration of Hinglish).

---

## 5. Data Contracts & Schemas

All schemas are JSON Schema **draft 2020-12**. Canonical copies live in `libs/vigil_common/schemas/*.schema.json` and are generated from Pydantic v2 models (`libs/vigil_common/models/`); CI fails if generated and committed schemas diverge. Common type notes:
- `uuid`: UUIDv7 string (time-ordered).
- `ts`: `{"type":"string","format":"date-time"}` with nanosecond fractional seconds allowed.
- `pseudo_id`: `^[A-Za-z0-9_-]{22,64}$` (base64url of truncated HMAC-SHA-256).
- `decimal_str`: `^-?\d+(\.\d{1,8})?$`.

### 5.1 `trade_tick.schema.json` (topic `market.trades.raw` / `market.trades.norm`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vigil.local/schemas/trade_tick/1.0.0",
  "title": "TradeTick",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version","event_id","exchange","symbol","trade_id","seq","ts_exchange","price","qty","aggressor_side","buyer","seller","is_synthetic"],
  "$defs": {
    "party": {
      "type": "object",
      "additionalProperties": false,
      "required": ["account_id","broker_id"],
      "properties": {
        "account_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]{22,64}$"},
        "broker_id": {"type": "string", "minLength": 1, "maxLength": 32},
        "gateway_id": {"type": "string", "maxLength": 64},
        "order_id": {"type": "string", "maxLength": 64},
        "device_fp": {"type": ["string","null"], "pattern": "^[A-Za-z0-9_-]{22,64}$"},
        "ip_hash": {"type": ["string","null"], "pattern": "^[A-Za-z0-9_-]{22,64}$"},
        "asn": {"type": ["integer","null"], "minimum": 0},
        "api_client_id": {"type": ["string","null"], "maxLength": 64},
        "order_to_ack_us": {"type": ["integer","null"], "minimum": 0}
      }
    }
  },
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "event_id": {"type": "string", "format": "uuid"},
    "exchange": {"enum": ["NSE","BSE","NASDAQ","NYSE","SYNTH"]},
    "symbol": {"type": "string", "pattern": "^[A-Z0-9&._-]{1,24}$"},
    "isin": {"type": ["string","null"], "pattern": "^[A-Z]{2}[A-Z0-9]{9}[0-9]$"},
    "trade_id": {"type": "string", "maxLength": 64},
    "seq": {"type": "integer", "minimum": 0},
    "ts_exchange": {"type": "string", "format": "date-time"},
    "ts_received": {"type": "string", "format": "date-time"},
    "ts_ingest": {"type": "string", "format": "date-time"},
    "price": {"type": "string", "pattern": "^\\d+(\\.\\d{1,8})?$"},
    "qty": {"type": "integer", "minimum": 1},
    "aggressor_side": {"enum": ["BUY","SELL","UNKNOWN"]},
    "buyer": {"$ref": "#/$defs/party"},
    "seller": {"$ref": "#/$defs/party"},
    "market_segment": {"enum": ["CASH","FNO","SME","OTHER"]},
    "is_synthetic": {"type": "boolean"},
    "scenario_label": {"type": ["string","null"], "description": "Ground-truth label, only when is_synthetic=true; stripped from agent inputs"},
    "ingest_latency_us": {"type": "integer", "minimum": 0}
  }
}
```

**Example**
```json
{
  "schema_version":"1.0.0","event_id":"0192f5c4-6a3e-7c21-9d4e-5b1a2c3d4e5f","exchange":"SYNTH","symbol":"ZENITHSME",
  "trade_id":"T-000184233","seq":184233,"ts_exchange":"2026-03-14T04:34:40.123456789Z",
  "price":"41.35","qty":1200,"aggressor_side":"BUY",
  "buyer":{"account_id":"Zx9fQ2mLpA7vT1kRwE4yBg","broker_id":"BRK-07","gateway_id":"GW-2","order_id":"O-9981","device_fp":"Dv3aK9pQ1xZ7mT2rWc8LsA","ip_hash":"Ip8tR2qW5yH1nB6cXe3KfG","asn":55836,"api_client_id":"algo-77","order_to_ack_us":812},
  "seller":{"account_id":"Qm1vB7nT3kP9xR5wL2cYdA","broker_id":"BRK-11","gateway_id":"GW-1","order_id":"O-9975"},
  "market_segment":"SME","is_synthetic":true
}
```

### 5.2 `l2_snapshot.schema.json` (topic `market.l2.raw` / `market.l2.norm`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vigil.local/schemas/l2_snapshot/1.0.0",
  "title": "L2Snapshot",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version","event_id","exchange","symbol","seq","ts_exchange","depth_levels","bids","asks","is_synthetic"],
  "$defs": {
    "level": {
      "type": "array", "prefixItems": [
        {"type":"string","pattern":"^\\d+(\\.\\d{1,8})?$","description":"price"},
        {"type":"integer","minimum":0,"description":"aggregate qty"},
        {"type":"integer","minimum":0,"description":"order count"}
      ], "minItems": 3, "maxItems": 3
    }
  },
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "event_id": {"type": "string", "format": "uuid"},
    "exchange": {"enum": ["NSE","BSE","NASDAQ","NYSE","SYNTH"]},
    "symbol": {"type": "string", "pattern": "^[A-Z0-9&._-]{1,24}$"},
    "seq": {"type": "integer", "minimum": 0},
    "ts_exchange": {"type": "string", "format": "date-time"},
    "ts_ingest": {"type": "string", "format": "date-time"},
    "depth_levels": {"type": "integer", "minimum": 5, "maximum": 50},
    "bids": {"type": "array", "items": {"$ref": "#/$defs/level"}, "maxItems": 50},
    "asks": {"type": "array", "items": {"$ref": "#/$defs/level"}, "maxItems": 50},
    "is_snapshot": {"type": "boolean", "default": true},
    "is_synthetic": {"type": "boolean"}
  }
}
```

### 5.3 `l3_order_event.schema.json` (topic `market.l3.raw` / `market.l3.norm`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vigil.local/schemas/l3_order_event/1.0.0",
  "title": "L3OrderEvent",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version","event_id","exchange","symbol","seq","ts_exchange","order_id","action","side","account_id","broker_id","is_synthetic"],
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "event_id": {"type": "string", "format": "uuid"},
    "exchange": {"enum": ["NSE","BSE","NASDAQ","NYSE","SYNTH"]},
    "symbol": {"type": "string", "pattern": "^[A-Z0-9&._-]{1,24}$"},
    "seq": {"type": "integer", "minimum": 0},
    "ts_exchange": {"type": "string", "format": "date-time"},
    "ts_ingest": {"type": "string", "format": "date-time"},
    "order_id": {"type": "string", "maxLength": 64},
    "orig_order_id": {"type": ["string","null"]},
    "action": {"enum": ["NEW","MODIFY","CANCEL","TRADE"]},
    "side": {"enum": ["BUY","SELL"]},
    "order_type": {"enum": ["LIMIT","MARKET","IOC","FOK"]},
    "price": {"type": ["string","null"], "pattern": "^\\d+(\\.\\d{1,8})?$"},
    "qty": {"type": "integer", "minimum": 0},
    "leaves_qty": {"type": "integer", "minimum": 0},
    "account_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]{22,64}$"},
    "broker_id": {"type": "string", "maxLength": 32},
    "gateway_id": {"type": "string", "maxLength": 64},
    "device_fp": {"type": ["string","null"]},
    "ip_hash": {"type": ["string","null"]},
    "asn": {"type": ["integer","null"]},
    "api_client_id": {"type": ["string","null"]},
    "order_to_ack_us": {"type": ["integer","null"], "minimum": 0},
    "is_synthetic": {"type": "boolean"}
  }
}
```

### 5.4 `social_message.schema.json` (topic `social.messages.raw`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vigil.local/schemas/social_message/1.0.0",
  "title": "SocialMessage",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version","event_id","platform","channel_id","message_id","author_id","ts_posted","text","channel_visibility","raw_sha256","is_synthetic"],
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "event_id": {"type": "string", "format": "uuid"},
    "platform": {"enum": ["telegram","discord","reddit","x","stocktwits","forum"]},
    "channel_id": {"type": "string", "maxLength": 96},
    "channel_name": {"type": "string", "maxLength": 256},
    "channel_visibility": {"enum": ["public","lawful_access"]},
    "channel_member_count": {"type": ["integer","null"], "minimum": 0},
    "message_id": {"type": "string", "maxLength": 96},
    "author_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]{22,64}$", "description": "pseudonymized handle id"},
    "author_display_hash": {"type": ["string","null"]},
    "ts_posted": {"type": "string", "format": "date-time"},
    "ts_ingest": {"type": "string", "format": "date-time"},
    "text": {"type": "string", "maxLength": 8192},
    "lang": {"type": ["string","null"], "pattern": "^[a-z]{2,3}(-[A-Za-z]+)?$"},
    "reply_to_message_id": {"type": ["string","null"]},
    "forwarded_from_channel_id": {"type": ["string","null"]},
    "views": {"type": ["integer","null"], "minimum": 0},
    "reactions": {"type": ["integer","null"], "minimum": 0},
    "urls": {"type": "array", "items": {"type": "string", "format": "uri"}, "maxItems": 20},
    "media_sha256": {"type": "array", "items": {"type": "string", "pattern": "^[a-f0-9]{64}$"}, "maxItems": 10},
    "raw_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "is_synthetic": {"type": "boolean"},
    "scenario_label": {"type": ["string","null"]}
  }
}
```

### 5.5 `social_signal.schema.json` (topic `social.signals.norm`, one record per message × ticker)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vigil.local/schemas/social_signal/1.0.0",
  "title": "SocialSignal",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version","signal_id","message_event_id","platform","channel_id","author_id","ts_posted","ticker","ticker_confidence","cta_class","urgency","raw_sha256","parser"],
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "signal_id": {"type": "string", "format": "uuid"},
    "message_event_id": {"type": "string", "format": "uuid"},
    "platform": {"type": "string"},
    "channel_id": {"type": "string"},
    "author_id": {"type": "string"},
    "ts_posted": {"type": "string", "format": "date-time"},
    "ts_processed": {"type": "string", "format": "date-time"},
    "ticker": {"type": "string", "pattern": "^[A-Z0-9&._-]{1,24}$"},
    "ticker_confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "mention_type": {"enum": ["CASHTAG","SYMBOL","COMPANY_NAME","ALIAS"]},
    "cta_class": {"enum": ["BUY_CALL","HOLD_PUMP","TARGET_PRICE","EXIT_SIGNAL","COORDINATION_TIMING","NEUTRAL"]},
    "cta_confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "target_price": {"type": ["string","null"], "pattern": "^\\d+(\\.\\d{1,8})?$"},
    "scheduled_action_time": {"type": ["string","null"], "format": "date-time"},
    "urgency": {"type": "number", "minimum": 0, "maximum": 1},
    "sentiment": {"type": "number", "minimum": -1, "maximum": 1},
    "near_dup_cluster_id": {"type": ["string","null"]},
    "forward_cascade_depth": {"type": "integer", "minimum": 0},
    "raw_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "parser": {
      "type": "object", "additionalProperties": false,
      "required": ["mode","version"],
      "properties": {
        "mode": {"enum": ["LLM","FALLBACK_RULES"]},
        "version": {"type": "string"},
        "llm_model": {"type": ["string","null"]},
        "prompt_sha256": {"type": ["string","null"]},
        "response_sha256": {"type": ["string","null"]}
      }
    }
  }
}
```

### 5.6 `anomaly_event.schema.json` (topics `anomaly.market`, `anomaly.social`, `anomaly.fused`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vigil.local/schemas/anomaly_event/1.0.0",
  "title": "AnomalyEvent",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version","anomaly_id","type","source_agent","symbol","window_start","window_end","score","severity","metrics","evidence_refs","detector_version","config_hash","detected_at"],
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "anomaly_id": {"type": "string", "format": "uuid"},
    "type": {"enum": ["VOLUME_SPIKE","SPREAD_WIDENING","DEPTH_IMBALANCE","SPOOFING_LAYERING","WASH_CYCLE","SYNCHRONIZED_ORDERS","PRICE_JUMP","HYPE_BURST","NEAR_DUPLICATE_CAMPAIGN","CROSS_MODAL_ALIGNMENT","FINGERPRINT_CLUSTER","CIRCULAR_RING","COORDINATED_VOLUME_LOOP"]},
    "source_agent": {"enum": ["quant_telemetry","social_intel","attribution","orchestrator"]},
    "symbol": {"type": "string"},
    "window_start": {"type": "string", "format": "date-time"},
    "window_end": {"type": "string", "format": "date-time"},
    "detected_at": {"type": "string", "format": "date-time"},
    "score": {"type": "number", "minimum": 0, "maximum": 1},
    "severity": {"enum": ["LOW","MEDIUM","HIGH","CRITICAL"]},
    "metrics": {"type": "object", "additionalProperties": {"type": ["number","string","boolean","array","object","null"]}},
    "participants": {"type": "array", "items": {"type": "string"}, "description": "account / handle pseudonyms"},
    "evidence_refs": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["kind","ref"],
        "properties": {
          "kind": {"enum": ["trade_id","order_id","l2_seq","social_message_id","raw_object_uri","anomaly_id"]},
          "ref": {"type": "string"},
          "sha256": {"type": ["string","null"]}
        }
      }
    },
    "detector_version": {"type": "string"},
    "config_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "case_id": {"type": ["string","null"], "format": "uuid"}
  }
}
```

**Example (`CROSS_MODAL_ALIGNMENT`)**
```json
{
  "schema_version":"1.0.0","anomaly_id":"0192f5d0-1111-7a00-8c00-aaaaaaaaaaaa","type":"CROSS_MODAL_ALIGNMENT",
  "source_agent":"orchestrator","symbol":"ZENITHSME","window_start":"2026-03-14T04:30:00Z","window_end":"2026-03-14T05:00:00Z",
  "detected_at":"2026-03-14T04:37:09.411Z","score":0.91,"severity":"CRITICAL",
  "metrics":{"best_lag_s":149,"xcorr_peak":0.78,"p_value":0.002,"hype_peak":88.4,"volume_z_peak":9.7},
  "participants":[],"evidence_refs":[{"kind":"anomaly_id","ref":"0192f5cf-...-hype"},{"kind":"anomaly_id","ref":"0192f5d0-...-vol"}],
  "detector_version":"aln-1.0.0","config_hash":"<64-hex>"
}
```

### 5.7 `forensic_dossier.schema.json` (output; table `dossiers`, object store `vigil-dossiers/`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://vigil.local/schemas/forensic_dossier/1.0.0",
  "title": "ForensicDossier",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version","dossier_id","version","case_id","generated_at","jurisdiction","subject","executive_summary","timeline","market_evidence","social_evidence","attribution","violated_clauses","confidence","limitations","evidence_manifest","merkle_root","ledger_anchor","signature","human_review"],
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "dossier_id": {"type": "string", "format": "uuid"},
    "version": {"type": "integer", "minimum": 1},
    "supersedes": {"type": ["string","null"], "format": "uuid"},
    "case_id": {"type": "string", "format": "uuid"},
    "generated_at": {"type": "string", "format": "date-time"},
    "jurisdiction": {"enum": ["SEBI_IN","SEC_US","GENERIC"]},
    "subject": {
      "type": "object", "additionalProperties": false,
      "required": ["symbol","exchange","window_start","window_end","manipulation_types"],
      "properties": {
        "symbol": {"type": "string"}, "exchange": {"type": "string"}, "isin": {"type": ["string","null"]},
        "window_start": {"type": "string", "format": "date-time"},
        "window_end": {"type": "string", "format": "date-time"},
        "manipulation_types": {"type": "array", "items": {"enum": ["PUMP_AND_DUMP","WASH_TRADING","CIRCULAR_TRADING","SPOOFING_LAYERING","COORDINATED_LIQUIDITY_SQUEEZE"]}, "minItems": 1}
      }
    },
    "executive_summary": {
      "type": "object", "additionalProperties": false, "required": ["text","citations"],
      "properties": {"text": {"type": "string", "maxLength": 4000}, "citations": {"type": "array", "items": {"type": "string"}, "minItems": 1}}
    },
    "timeline": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["ts","track","description","evidence_ids"],
        "properties": {
          "ts": {"type": "string", "format": "date-time"},
          "track": {"enum": ["SOCIAL","MARKET","GRAPH","SYSTEM"]},
          "description": {"type": "string", "maxLength": 1000},
          "evidence_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}
        }
      }
    },
    "market_evidence": {
      "type": "object", "additionalProperties": false,
      "required": ["total_volume","suspect_volume","suspect_volume_ratio","anomalies","price_move_pct"],
      "properties": {
        "total_volume": {"type": "integer"}, "suspect_volume": {"type": "integer"},
        "suspect_volume_ratio": {"type": "number", "minimum": 0, "maximum": 1},
        "price_move_pct": {"type": "number"},
        "anomalies": {"type": "array", "items": {"type": "string"}}
      }
    },
    "social_evidence": {
      "type": "object", "additionalProperties": false,
      "required": ["channels","message_count","hype_peak","cta_breakdown","near_duplicate_campaigns"],
      "properties": {
        "channels": {"type": "array", "items": {"type": "string"}},
        "message_count": {"type": "integer"}, "hype_peak": {"type": "number"},
        "cta_breakdown": {"type": "object", "additionalProperties": {"type": "integer"}},
        "near_duplicate_campaigns": {"type": "integer"},
        "alignment": {"type": "object", "properties": {"best_lag_s": {"type": "number"}, "xcorr_peak": {"type": "number"}, "p_value": {"type": "number"}}}
      }
    },
    "attribution": {
      "type": "object", "additionalProperties": false, "required": ["rings","leads"],
      "properties": {
        "rings": {"type": "array", "items": {
          "type": "object", "additionalProperties": false,
          "required": ["ring_id","entity_id","ring_score","accounts","methods","cycle_count","net_volume","evidence_ids"],
          "properties": {
            "ring_id": {"type": "string"}, "entity_id": {"type": "string"},
            "ring_score": {"type": "number", "minimum": 0, "maximum": 1},
            "accounts": {"type": "array", "items": {"type": "string"}, "minItems": 2},
            "methods": {"type": "array", "items": {"enum": ["SHARED_DEVICE","SHARED_NETWORK","SHARED_KYC","LATENCY_SIGNATURE","BROKER_PATHWAY","CIRCULAR_CYCLE","SYNCHRONIZED_ORDERS","REACTION_LATENCY"]}},
            "cycle_count": {"type": "integer"}, "net_volume": {"type": "integer"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}
          }}},
        "leads": {"type": "array", "items": {"type": "object", "properties": {"account_id": {"type": "string"}, "confidence": {"type": "number"}, "note": {"type": "string"}}}}
      }
    },
    "violated_clauses": {
      "type": "array", "items": {
        "type": "object", "additionalProperties": false,
        "required": ["regime","clause_id","title","finding_types","rationale","legal_review_required"],
        "properties": {
          "regime": {"enum": ["SEBI","SEC"]}, "clause_id": {"type": "string"}, "title": {"type": "string"},
          "finding_types": {"type": "array", "items": {"type": "string"}},
          "rationale": {"type": "string"}, "evidence_ids": {"type": "array", "items": {"type": "string"}},
          "legal_review_required": {"type": "boolean"}
        }}
    },
    "confidence": {
      "type": "object", "additionalProperties": false, "required": ["overall","completeness","components"],
      "properties": {"overall": {"type": "number", "minimum": 0, "maximum": 1}, "completeness": {"type": "number", "minimum": 0, "maximum": 1}, "components": {"type": "object", "additionalProperties": {"type": "number"}}}
    },
    "limitations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "evidence_manifest": {
      "type": "array", "minItems": 1, "items": {
        "type": "object", "additionalProperties": false,
        "required": ["evidence_id","type","sha256","uri","bytes","captured_at"],
        "properties": {
          "evidence_id": {"type": "string"},
          "type": {"enum": ["TRADE_SLICE","L2_SLICE","L3_SLICE","SOCIAL_SLICE","GRAPH_EXPORT","CHART_IMAGE","ANOMALY_EVENT","LLM_TRACE","CONFIG_SNAPSHOT"]},
          "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
          "uri": {"type": "string"}, "bytes": {"type": "integer"},
          "captured_at": {"type": "string", "format": "date-time"}
        }}
    },
    "merkle_root": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "ledger_anchor": {
      "type": "object", "additionalProperties": false, "required": ["entry_id","entry_hash","prev_entry_hash"],
      "properties": {"entry_id": {"type": "integer"}, "entry_hash": {"type": "string"}, "prev_entry_hash": {"type": "string"}, "tsa_token_b64": {"type": ["string","null"]}}
    },
    "signature": {
      "type": "object", "additionalProperties": false, "required": ["alg","key_id","canonicalization","digest_sha256","value_b64","signed_at"],
      "properties": {
        "alg": {"const": "Ed25519"}, "key_id": {"type": "string"}, "canonicalization": {"const": "RFC8785-JCS"},
        "digest_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "value_b64": {"type": "string"}, "signed_at": {"type": "string", "format": "date-time"}
      }
    },
    "human_review": {
      "type": "object", "additionalProperties": false, "required": ["status"],
      "properties": {
        "status": {"enum": ["NOT_REVIEWED","APPROVED","REJECTED","REWORK"]},
        "reviewer_id": {"type": ["string","null"]}, "reviewed_at": {"type": ["string","null"], "format": "date-time"}, "comment": {"type": ["string","null"]}
      }
    }
  }
}
```

**Signing rule (normative):** `digest = SHA256(JCS(dossier minus the "signature" member))`; `signature.value = Ed25519_sign(privkey, digest_bytes)`. The `signature.digest_sha256` is the hex of `digest`. The `human_review` member **is** included in the signed payload; therefore approval triggers a new version.

---

## 6. Milestones & Acceptance Criteria

### 6.1 Milestone plan (MVP = M0–M8)

| Milestone | Scope | Exit criteria (summary) |
|---|---|---|
| **M0 — Scaffold** | Monorepo, Docker Compose, CI, schemas, shared lib, migrations | `make up` healthy; `make test` green; schema contract tests pass |
| **M1 — Market ingestion** | Synthetic feed, ingestion service, Kafka topics, Timescale writers, DLQ | AC-ING-* |
| **M2 — Social ingestion & hype** | Social adapters, semantic parser (LLM + fallback), hype scorer | AC-SOC-* |
| **M3 — Quant telemetry** | All QTA detectors | AC-QTA-* |
| **M4 — Cross-modal alignment** | Alignment engine, MRS, case-opening trigger | AC-ALN-* |
| **M5 — Graph attribution** | Neo4j loaders, fingerprint clustering, cycle/ring detection | AC-GRA-* |
| **M6 — Orchestrator & evidence** | LangGraph state machine, dossier builder, signer, ledger, verifier | AC-ORC-*, AC-DOS-* |
| **M7 — Dashboard** | All routes in FR-UI | AC-UI-* |
| **M8 — Hardening** | Load test, chaos test, security checks, docs | AC-NFR-* |

### 6.2 Definition of Done for the MVP (all MUST pass)

**Ingestion**
- **AC-ING-01** Running scenario `baseline_01` for 10 simulated minutes at 5,000 ev/s yields **0 events in DLQ** and p99 `vigil_ingest_latency_seconds` < 0.200.
- **AC-ING-02** Injecting 100 malformed events produces exactly 100 DLQ records, each with a non-empty `error` field.
- **AC-ING-03** Injecting a sequence gap emits one `SEQ_GAP` health event within 2 s.
- **AC-ING-04** Replaying the same file twice results in unchanged row counts in `trades` (idempotency).

**Social**
- **AC-SOC-01** On the labelled corpus `datasets/social_labeled_v1.jsonl` (≥ 500 messages), ticker-extraction F1 ≥ 0.92 and CTA macro-F1 ≥ 0.80 in LLM mode; ≥ 0.85 and ≥ 0.70 in fallback mode.
- **AC-SOC-02** With `ANTHROPIC_API_KEY` unset or the LLM endpoint blocked, the pipeline continues in `FALLBACK_RULES` mode with no crash and `parser.mode` reflects it.
- **AC-SOC-03** In scenario `pump_dump_ring_01`, a `HYPE_BURST` for `ZENITHSME` is emitted within 60 s of the first coordinated message, and none are emitted on `baseline_01`.

**Quant**
- **AC-QTA-01** Scenario `pump_dump_ring_01` yields `VOLUME_SPIKE` and `PRICE_JUMP` on the target symbol; `baseline_01` yields ≤ 1 false anomaly per simulated 6 h per symbol-tier.
- **AC-QTA-02** Scenario `wash_ring_01` yields ≥ 90 % of injected wash cycles as `WASH_CYCLE` events (recall) with precision ≥ 0.85.
- **AC-QTA-03** Scenario `spoofing_01` yields `SPOOFING_LAYERING` for each injected spoofer account (recall ≥ 0.9).

**Alignment & Case**
- **AC-ALN-01** In `pump_dump_ring_01`, `CROSS_MODAL_ALIGNMENT` is emitted with `best_lag_s` within ±30 s of the simulator's ground-truth lag, and a Case is auto-opened within 10 s.
- **AC-ALN-02** On `baseline_01` no Case is opened over 30 simulated minutes (with seeds 1–5).

**Graph**
- **AC-GRA-01** In `pump_dump_ring_01` (20 ring accounts across 3 brokers, 5 shared devices, 1 shared ASN), the system recovers the ring with account-level precision ≥ 0.85 and recall ≥ 0.90, producing a single `Entity` with `ring_score ≥ 0.8`.
- **AC-GRA-02** The Cypher cycle query (ARCHITECTURE §6.4) returns all injected cycles (length 2–5) and no cycles on `baseline_01`.
- **AC-GRA-03** Graph API response for the demo case < 800 ms p95 (N=100 requests).

**Orchestration & Dossier**
- **AC-ORC-01** A Case traverses `OPENED → … → PENDING_REVIEW` automatically in < 5 min on `pump_dump_ring_01`.
- **AC-ORC-02** Killing the orchestrator container mid-case and restarting resumes the case without duplicating ledger entries.
- **AC-ORC-03** With the LLM blocked, dossier is still produced via the deterministic template (`dossier.narrative_mode = "TEMPLATE"` recorded in `LLM_TRACE`/config evidence).
- **AC-DOS-01** The generated dossier validates against `forensic_dossier.schema.json`; every timeline entry and executive-summary citation resolves to an `evidence_manifest` entry.
- **AC-DOS-02** `POST /api/v1/verify` on the exported bundle returns `{"valid": true}`; flipping any single byte in any evidence file or in the dossier JSON returns `{"valid": false}` with the failing check named (`HASH_MISMATCH`, `MERKLE_MISMATCH`, `LEDGER_CHAIN_BROKEN`, `SIGNATURE_INVALID`).
- **AC-DOS-03** Attempting `UPDATE`/`DELETE` on `evidence_ledger` via SQL raises an exception.
- **AC-DOS-04** The offline CLI `vigil-verify <bundle.zip> --pubkey keys/dev_ed25519.pub` returns exit code 0 on valid bundles and non-zero otherwise.
- **AC-DOS-05** PDF export renders ≥ 6 sections, embeds the manifest hash and a verification QR code, and opens without errors in a standards-compliant viewer.
- **AC-DOS-06** A case cannot be moved to `PUBLISHED` via API without a `compliance_officer` approval (HTTP 409 otherwise).

**UI**
- **AC-UI-01** All routes in FR-UI-01…08 render without console errors; Playwright e2e suite `frontend/e2e/*.spec.ts` passes in CI.
- **AC-UI-02** Graph explorer renders a 500-node graph at ≥ 30 fps on a mid-range laptop.

**Non-functional**
- **AC-NFR-01** `make load-test` sustains NFR-PERF-02 for 15 min with p99 < 200 ms.
- **AC-NFR-02** Chaos test: killing Kafka consumer, Neo4j, or Redis for 60 s causes no event loss (verified by row-count reconciliation) and the system recovers automatically.
- **AC-NFR-03** `make smoke` completes end-to-end in < 10 minutes on the reference environment, exit code 0.
- **AC-NFR-04** `mypy --strict`, `ruff`, `pytest` (≥ 80 % coverage on `services/agents/**` detectors) all pass in CI.

### 6.3 Synthetic scenario catalogue (ground truth for acceptance)

| Scenario ID | Description | Ground-truth artefacts |
|---|---|---|
| `baseline_01` | 40 symbols, organic flow, ambient chatter, no manipulation | None |
| `pump_dump_ring_01` | SME ticker `ZENITHSME`; 3 Telegram channels coordinate at T0; 20 ring accounts (3 brokers, 5 devices, 1 ASN) buy from T0+150 s; price +38 %; dump from T0+14 min | `ring_accounts[]`, `lag_s=150`, `dump_start` |
| `wash_ring_01` | 6 accounts trade in 2- to 5-cycles with matched qty | `cycles[]` |
| `spoofing_01` | 2 accounts layer 8 orders then cancel after opposite-side fills | `spoofers[]` |
| `liquidity_squeeze_01` | Coordinated withdrawal of depth followed by synchronized aggressive buys | `squeeze_window` |
| `adversarial_noise_01` | Genuine news-driven spike with organic social surge (should NOT open a case, or open with LOW confidence) | `expected_cases=0` |

---

## 7. Open Questions & Assumptions
1. **Real exchange feeds** expose counterparty identifiers only to the regulator/exchange; the MVP assumes such a privileged feed is available through an adapter. Public-only deployments would degrade to behavioural (non-identity) detection.
2. **Clause mappings** are advisory and require legal vetting per jurisdiction before operational use.
3. **LLM usage** is limited to semantic enrichment and narrative drafting; all numeric findings are computed deterministically.
4. **Private-channel monitoring** requires legal authority and is explicitly excluded from MVP defaults.
