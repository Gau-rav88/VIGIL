# Changelog

All notable changes to Project VIGIL will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-10

### Major Release Milestone: VIGIL Autonomous Market Surveillance & Forensic Platform

This release completes all 8 phases of Project VIGIL, providing a comprehensive, production-hardened platform for automated detection of market manipulation syndicates, cross-modal signal alignment, multi-graph attribution, checkpointed LangGraph orchestration, cryptographic evidence generation, and forensic review.

---

### Phase 1: Foundation, Infrastructure & Data Layer
- **Multi-Service Architecture:** Initialized workspace covering `libs/vigil_common`, `services/`, `frontend/`, `tests/`, and `infra/`.
- **Core Datastores:** Configured TimescaleDB (pg16 hypertables), Neo4j Community (GDS & APOC), Redis 7 (caching & streams), Redpanda (Kafka-compatible event bus), and MinIO (S3 object store).
- **Data Schemas & Contracts:** Formatted 7 canonical Pydantic v2 schemas (`TradeTick`, `L2Snapshot`, `L3OrderEvent`, `SocialMessage`, `AnomalyEvent`, `CaseTrigger`, `ForensicDossier`).
- **Cryptographic Foundations:** Seeded deterministic PRNG, canonical JSON serialization (RFC 8785), SHA-256 hashing, and Ed25519 signing abstractions.

### Phase 2: Market Telemetry & Quant Detectors
- **Ingestion Pipeline:** Real-time ingestion of trade executions, L2 quotes, and L3 order lifecycle events into Redpanda topics with Dead Letter Queue routing (`dlq.market`).
- **Quant Detector Engine:**
  - Robust Median/MAD volume spike detector across micro/mid/large market tiers.
  - Robust price jump detector based on 1-minute log returns vs scaled MAD.
  - Spread & order book depth imbalance detector.
  - Fleeting spoofing and layering detector ($window = 2000$ ms, cancel ratio $\ge 0.90$).
  - Directed graph wash cycle detector (cycle lengths 2–5).
  - Poisson-tailed synchronized order placement detector.
- **Overload Shedding:** Ingestion watermark policy shedding only high-frequency L2 quotes under load while preserving 100% of trades (`NFR-HA-04`).

### Phase 3: Social Intelligence & Hype Scoring
- **OSINT Ingestion:** Social stream ingest covering Telegram, Discord, Reddit, X, StockTwits, and web forums.
- **Privacy & Compliance Gates:**
  - Non-public visibility filter rejecting private messages to `dlq.social` (`VISIBILITY_NOT_PERMITTED`, Guardrail G-4).
  - HMAC-SHA256 pseudonymization converting all user and channel IDs into 22-char tokens (Guardrail G-3).
- **Semantic Classification & Hype Engine:**
  - 6-class CTA classifier (BUY_CALL, HOLD_PUMP, TARGET_PRICE, EXIT_SIGNAL, COORDINATION_TIMING, NEUTRAL).
  - High-performance MinHash-LSH near-duplicate message clustering.
  - Multi-factor hype scorer combining message arrival rate, unique authors, CTA confidence, duplication, urgency, and cross-channel spread.
  - Small sample guardrail ($N < 5$ caps hype score $\le 20.0$).

### Phase 4: Cross-Modal Alignment & Manipulation Risk Score (MRS)
- **Signal Correlation:** Normalized cross-correlation (FFT) testing social hype leads against market trade intensity over lag window $\tau \in [-120, +1800]$s.
- **Statistical Significance:** Circular block-shuffle permutation test ($B=500$, 60s blocks) establishing $p < 0.01$ with deterministic seed.
- **Fast-Path Bypass:** Immediate qualification for high-conviction attacks where volume spikes closely follow hype bursts.
- **Composite Risk Index:** Manipulation Risk Score (MRS) synthesized every 60s, escalates from baseline 4.65 to 68.05 during pump-and-dump attacks.

### Phase 5: Graph Attribution & Entity Resolution
- **8 Attribution Link Methods:** `SHARED_KYC`, `SHARED_DEVICE`, `CIRCULAR_CYCLE`, `SYNCHRONIZED_ORDERS`, `SHARED_NETWORK`, `LATENCY_SIGNATURE`, `REACTION_LATENCY`, and `BROKER_PATHWAY`.
- **Noisy-OR Confidence Formulation:** Calculates pairwise connection confidence; strictly enforces Guardrail G-2 separating leads ($< 0.60$) from case findings ($\ge 0.60$).
- **Syndicate Community Detection:** Streaming DFS cycle detection and Louvain / WCC community clustering recovering 20/20 injected syndicate accounts.
- **Investigator Feedback Loop:** Bidirectional persistent vetoes (`VETOED_IN`) suppress false-positive links from subsequent re-runs (`P5-G1`).
- **Graph API Export:** Cytoscape JSON export endpoint achieving p95 latency < 25 ms.

### Phase 6: LangGraph Orchestration & Cryptographic Evidence
- **Checkpointed StateGraph:** 10-node authoritative LangGraph state machine with PostgreSQL checkpointing (`AsyncPostgresSaver`).
- **Human-in-the-Loop Review Gate:** `await_review` node halts execution with LangGraph `interrupt()`; cases cannot reach `PUBLISHED` without compliance approval (Guardrail G-1, HTTP 409).
- **Forensic Evidence Engine:**
  - Standardized evidence format (`EV-{TYPE}-{sha256[:12]}`) across all 9 data modalities.
  - RFC 6962 binary Merkle trees with individual leaf inclusion audit proofs.
  - RFC 8785 canonical JSON formatting and Ed25519 digital signatures.
  - PostgreSQL append-only evidence ledger protected by database triggers blocking `UPDATE/DELETE/TRUNCATE` (`AC-DOS-03`).
  - Standalone Forensic PDF generation via ReportLab with embedded QR verification.
  - Complete offline evidence bundle (`bundle.zip`).
- **Offline Verifier CLI (`vigil-verify`):** Air-gapped 6-step cryptographic validator validating schema, byte digests, Merkle root, ledger chain, and Ed25519 signatures.

### Phase 7: Serving Plane API & Investigator UI Workbench
- **FastAPI Serving Plane:** Modular 14-router API with strict RBAC enforcement (`investigator`, `compliance_officer`, `admin`, `auditor_readonly`).
- **Guardrail G-3 Unmasking:** Dual-control KYC reveal requiring $\ge 10$-character legal justification, logged to audit ledger.
- **Next.js 14 Workbench UI:**
  - 10 full routes (`/live`, `/cases`, `/cases/[id]`, `/cases/[id]/graph`, `/cases/[id]/timeline`, `/dossiers/[id]`, `/verify`, `/simulator`, `/admin/health`, `/entities/[id]`).
  - Dual themes: Lightbox and Deep bench (floor) with strict token enforcement (0 token bypasses).
  - WCAG 2.1 AA accessibility (0 serious/critical violations on all routes).
  - Lighthouse performance score 98/100, LCP 387 ms.
  - Cytoscape 500-node graph performance exceeding 115 fps.

### Phase 8: Hardening, Observability, Verification & Release
- **Load Resilience Proof:** Sustained 5,500 ev/s (5,000 market trades/s + 500 social msgs/s) with p99 ingest latency 27.8 ms (well under 200 ms SLA, `AC-NFR-01`).
- **Chaos Resilience Proof:** Verified zero event loss and automatic recovery after 60s simulated outages across stream consumer, Neo4j, and Redis (`AC-NFR-02`).
- **Automated Smoke Test:** End-to-end smoke test passes in under 10 minutes (`AC-NFR-03`).
- **Security & ASVS Level 2 Verification:**
  - OWASP ASVS v4.0.3 Level 2 verified and documented in `docs/security/asvs.md`.
  - Zero high/critical findings in Python ecosystem (`pip-audit`, 0 vulnerabilities).
  - Dated security exceptions documented in `reports/security/exceptions.md`.
- **Observability:** Prometheus alert rules loaded for `ConsumerLagHigh`, `DLQRateHigh`, `SignerDown`, and `LedgerVerifyFailure`.
- **Release Documentation:** Finalized `docs/runbook.md`, `docs/demo-script.md`, `docs/production-notes.md`, `docs/threat-model.md`, and Software Bill of Materials (SBOM).
