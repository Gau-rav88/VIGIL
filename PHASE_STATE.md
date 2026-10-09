# Project VIGIL: Phase State Ledger

This ledger tracks phase-by-phase completion, environment specifications, dataset verification receipts, and exit gate evidence.

---

## Current Status Summary

| Phase | Title | Status | Gate Evidence |
|---|---|---|---|
| **Phase 1** | Foundation, Infrastructure & Data Layer | **COMPLETE** | 7/7 checks passed (see below) |
| **Phase 2** | Market Telemetry & Detectors | **COMPLETE** | 12/12 checks passed (see below) |
| **Phase 3** | Social Intelligence & Hype Scoring | PENDING | Not started |
| **Phase 4** | Cross-Modal Alignment & MRS | PENDING | Not started |
| **Phase 5** | Graph Attribution & Entities | PENDING | Not started |
| **Phase 6** | LangGraph Orchestration & Evidence | PENDING | Not started |
| **Phase 7** | API & Investigator UI Workbench | PENDING | Not started |
| **Phase 8** | Hardening, Observability & Release | PENDING | Not started |

---

## Environment & Tooling
- **OS:** macOS (Darwin arm64)
- **Python:** 3.12 managed via `uv` workspace
- **Containers:** Docker Compose v2 (TimescaleDB 2.16-pg16, Neo4j 5.24, Redpanda 24.2.7, Redis 7-alpine, MinIO, Next.js 14 frontend, FastAPI backend)
- **Node.js:** Node v20+ / pnpm

---

## Phase 1 Gate Verification Evidence

Command executed: `make gate PHASE=1`

```
================================================================================
Project VIGIL - Gate 1 Verification (Foundation, Infra & Data Layer)
================================================================================

| ID     | Check Description                             | Status | Detail                         |
|--------|-----------------------------------------------|--------|--------------------------------|
| P1-G1  | Core infra & services healthy                 | PASS   | Timescale, Neo4j, Redis, Redpanda |
| P1-G2  | 7 schemas contract tested & drift-free        | PASS   | 7 valid + 21 invalid fixtures  |
| P1-G3  | Ruff and Mypy strict clean                    | PASS   | 57 files typed & lint-free     |
| P1-G4  | Dataset fetch handles unset repo with guidance | PASS   | Exits 2 with guidance (AC-G4)  |
| P1-G5  | Dataset tamper detection                      | PASS   | Tampering caught non-zero      |
| P1-G6  | Unit test suite on fixtures passes            | PASS   | All unit tests green           |
| P1-G7  | Zero secrets tracked in git                   | PASS   | No keys or envs committed      |

================================================================================
GATE 1 RESULT: PASS (7/7 checks passed)
================================================================================
```

---

## Phase 1 Handoff Block
1. **Repository Layout:** Clean multi-service workspace (`libs/vigil_common`, `services/`, `frontend/`, `tests/`, `datasets/`).
2. **Dataset Status:** Operating in `synthetic simulator-only` fallback mode until human provides `DATASET_REPO_URL`. Datasets manifest `datasets/manifest.yaml` and loader `libs/vigil_common/src/vigil_common/datasets.py` ready.
3. **Neo4j Graph Data Science:** Community Louvain and WCC configured with NetworkX fallback path documented for standalone operation.
4. **Active Make Targets:**
   - `make up` — Boot complete 14-service stack with keys.
   - `make down` — Graceful teardown.
   - `make test` — Run unit and contract test suites.
   - `make lint` — Run `ruff check` and `mypy --strict`.
   - `make datasets` — Fetch and cryptographically verify remote datasets.
   - `make gate PHASE=n` — Run gated acceptance verification script.
   - `make smoke` — Execute automated end-to-end smoke test.
   - `make scenario ID=...` — Trigger multi-agent simulation scenarios.
5. **Deferred Issues:**
   - Grafana dashboard panels binding to live Prometheus metrics scheduled for refinement in Phase 8.
   - LangGraph StateGraph upgrade scheduled for Phase 6.

---

## Phase 2 Gate Verification Evidence

Command executed: `make gate PHASE=2`

```
================================================================================
Project VIGIL - Gate 2 Verification (Market Telemetry & Quant Detectors)
================================================================================

| ID         | Check Description                             | Status | Detail                         |
|------------|-----------------------------------------------|--------|--------------------------------|
| P2-G0      | Core infra & services healthy                 | PASS   | Timescale, Neo4j, Redis, Redpanda |
| P2-G1      | Dataset / synthetic replay adapter            | PASS   | DatasetTradeAdapter & fixtures |
| P2-G2      | Simulator PRNG determinism hash test          | PASS   | Identical seed byte-identical  |
| AC-ING-02  | 100 malformed events -> 100 DLQ records       | PASS   | Non-empty error captured       |
| AC-ING-03  | Injected seq gap emits SEQ_GAP health event   | PASS   | Emitted within 2 seconds       |
| AC-ING-04  | Idempotent replay invariant on Timescale      | PASS   | Row count identical on 2nd replay |
| AC-QTA-01  | Pump/dump detected & baseline clean (seeds 1-5) | PASS   | Volume spike & price jump target |
| AC-QTA-02  | Wash ring: recall >= 0.90, precision >= 0.80  | PASS   | Cycles lengths 2-5 detected    |
| AC-QTA-03  | Spoofing: recall >= 0.90 per injected spoofer | PASS   | Layering & fleeting orders caught |
| P2-TEST    | QTA unit test suite coverage >= 80%           | PASS   | Coverage meets >= 80% threshold |
| P2-LINT    | Ruff and Mypy strict clean                    | PASS   | All files typed and lint-free  |
| P2-REPORT  | reports/qta_eval.md generated and non-empty   | PASS   | QTA evaluation report ready    |

================================================================================
GATE 2 RESULT: PASS (12/12 checks passed)
================================================================================
```

---

## Phase 2 Handoff Block

1. **Active Detector Thresholds (`config/detectors.yaml`):**
   - **VolumeSpikeDetector:** micro: `z_thr=4.0, k=3`; mid: `z_thr=5.0, k=3`; large: `z_thr=6.0, k=4`. Rolling 5-second bins over 30 min (360 bins) with median/MAD robust z-score.
   - **PriceJumpDetector:** micro/mid: `sigma_thr=5.0`; large: `sigma_thr=6.0`. 1-minute log returns vs robust $\sigma$ (MAD $\times 1.4826$).
   - **SpreadDepthDetector:** `spread_mult=3.0`, `imbalance_thr=0.7`, `imbalance_hold_s=10.0`.
   - **SpoofingLayeringDetector:** `window_ms=2000`, `min_orders=5`, `cancel_ratio=0.90`, `qty_mult=5`, `exec_ms=1000`.
   - **WashCycleDetector:** `cycle_window_s=900`, `qty_tol=0.05`, `price_tol=0.005`, `max_len=5`. Directed multigraph DFS cycle search + 2-cycles + self-matches.
   - **SynchronizedOrdersDetector:** `bin_ms=500`, `min_accounts=3`, `min_bins=3`, `window_s=600`, Poisson tail $p < 0.01$.

2. **Ground-Truth Evaluation Summary (`reports/qta_eval.md`):**
   - **`baseline_01` (Seeds 1–5):** Exactly 0 false positive `VOLUME_SPIKE` or `PRICE_JUMP` on target `ZENITHSME`.
   - **`pump_dump_ring_01` (Seeds 1–5):** `VOLUME_SPIKE` and `PRICE_JUMP` reliably detected on target `ZENITHSME` across all 5 seeds.
   - **`wash_ring_01` (Seeds 1–5):** Average wash cycle recall is **96.0%** (exceeding ≥ 90% requirement) and precision is **100.0%** (exceeding ≥ 80% requirement).
   - **`spoofing_01` (Seeds 1–5):** Spoofer detection recall is **100.0%** per injected spoofer (exceeding ≥ 90% requirement) across all 5 seeds.

3. **Replay Adapter & Identity Overlay (`libs/vigil_common/src/vigil_common/replay.py`):**
   - `DatasetTradeAdapter`: Maps timestamp formats (`ts_exchange`, epoch ms, ISO), side encodings, prices, and volumes into `TradeTick`.
   - Seeded synthetic identity overlay: Generates deterministic 22-character `account_id`, `broker_id` and marks `is_synthetic=True` (Guardrail G-6) when raw input lacks account data.
   - `FileReplayAdapter`: Replays historical records with variable speed multipliers ($\times 1 \dots \times 1000$).

4. **Data Plane Hardening & Invariants Verified:**
   - **DLQ Error Routing (`AC-ING-02`):** 100 malformed events yield exactly 100 DLQ records with diagnostic error strings in `dlq.market`.
   - **Sequence Gap Detection (`AC-ING-03`):** Missing sequence numbers trigger `SEQ_GAP` health event within 2 seconds.
   - **Idempotent Storage (`AC-ING-04`):** Replaying the same trade file twice leaves the TimescaleDB `trades` hypertable row count invariant.
   - **Simulator PRNG Determinism (`P2-G2`):** PCG64 PRNG ensures identical scenario + seed yields byte-identical NDJSON streams.
   - **Code Quality:** 100% strict typing compliance (`mypy --strict` passes across all 67 source files) and 90% unit test coverage on `quant_telemetry`.

