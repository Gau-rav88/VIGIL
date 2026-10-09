# Project VIGIL

### Autonomous Multi-Agent Forensic Intelligence Platform for Capital-Market Manipulation

**VIGIL** (*Versatile Intelligence for Gathering Illicit-trading Linkages*) compresses the market manipulation investigation lifecycle from months to minutes by fusing high-frequency order-book telemetry (L2/L3/trades) with public social/OSINT signals (Telegram, Discord, Reddit, X, forums). It automatically unmasks coordinated trading syndicates, generates explainable forensic graph attributions, and compiles cryptographically signed, court-admissible dossiers (PDF + JSON) with an investigator in the loop.

---

## Documentation

- **[PRD.md](PRD.md)** — Requirements v2.0.0, functional specifications, data schemas, 8 gated phases, and acceptance criteria.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Technical source of truth, topology, algorithms, Cypher queries, data contracts, and implementation blueprints.
- **[FLOW.md](FLOW.md)** — End-to-end data and decision hops $S0 \to S13$, scenario walkthroughs, and error recovery.
- **[FRONTEND.md](FRONTEND.md)** — UI design specifications, design tokens, screen layouts, and component architecture.
- **[PHASE_STATE.md](PHASE_STATE.md)** — Live progress ledger tracking environment state, dataset receipts, and phase gate results.

---

## 8 Gated Phases

| Phase | Description | Gate Command |
|---|---|---|
| **Phase 1** | Foundation, Infrastructure & Data Layer | `make gate PHASE=1` |
| **Phase 2** | Market Microstructure Telemetry & Detectors | `make gate PHASE=2` |
| **Phase 3** | Social Intelligence & Semantic Parsing | `make gate PHASE=3` |
| **Phase 4** | Cross-Modal Temporal Alignment & MRS | `make gate PHASE=4` |
| **Phase 5** | Cyber-Forensics Graph Attribution | `make gate PHASE=5` |
| **Phase 6** | LangGraph Orchestration & Cryptographic Evidence | `make gate PHASE=6` |
| **Phase 7** | REST/WS Gateway & Investigator UI Workbench | `make gate PHASE=7` |
| **Phase 8** | Hardening, Observability, Verification & Release | `make gate PHASE=8` |

---

## Core Capabilities

1. **Market Microstructure Telemetry Ingestion**: High-throughput validation, sequence monitoring, and microsecond latency stamping for trades, L2 snapshots, and L3 order feeds.
2. **Social Intelligence & Hype Bursts**: Dual-path parsing (fast multilingual regex/lexicon + async bounded LLM refinement) and 5s multi-factor sliding `hype_score`.
3. **Cross-Modal Temporal Alignment**: Normalized cross-correlation with circular-block permutation testing ($p < 0.01$) to detect when social hype leads market volume spikes.
4. **Cyber-Forensics Graph Attribution**: Neo4j property graph tracking wash trading cycles, synchronized order groups, device/network fingerprints, and Louvain-partitioned syndicates.
5. **Deterministic LangGraph Orchestration**: Checkpointed state machine managing the case lifecycle with automated fallbacks and human-in-the-loop review gating.
6. **Evidentiary Chain of Custody**: Append-only hash-chained ledger, RFC 6962 Merkle trees, RFC 8785 JCS canonicalization, Ed25519 digital signatures, and WeasyPrint court-ready PDFs.
7. **Full-Stack Serving & UI**: FastAPI backend with WebSockets and Next.js 14 dashboard (Recharts timeline, Cytoscape.js interactive graph, and drag-and-drop bundle verifier).

---

## Quickstart

### Prerequisites
- Docker $\ge 25$ with Docker Compose v2 (recommended: 8 vCPUs / 16 GB RAM).
- Python 3.12 managed via `uv`.
- Node.js $\ge 20$ managed via `pnpm`.

### Setup & Run
```bash
# 1. Generate dev Ed25519 keys and start services
make up

# 2. Access Web UI & API
# Dashboard:     http://localhost:3000
# API & Docs:    http://localhost:8000/docs
# Redpanda:      http://localhost:8080
# Neo4j:         http://localhost:7474
# MinIO:         http://localhost:9001

# 3. Trigger a simulation scenario
make scenario ID=pump_dump_ring_01 SPEED=10 SEED=42

# 4. Run automated end-to-end smoke acceptance
make smoke
```
