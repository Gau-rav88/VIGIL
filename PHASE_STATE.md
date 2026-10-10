# Project VIGIL: Phase State Ledger

This ledger tracks phase-by-phase completion, environment specifications, dataset verification receipts, and exit gate evidence.

---

## Current Status Summary

| Phase | Title | Status | Gate Evidence |
|---|---|---|---|
| **Phase 1** | Foundation, Infrastructure & Data Layer | **COMPLETE** | 7/7 checks passed (see below) |
| **Phase 2** | Market Telemetry & Detectors | **COMPLETE** | 12/12 checks passed (see below) |
| **Phase 3** | Social Intelligence & Hype Scoring | **COMPLETE** | 10/10 checks passed (see below) |
| **Phase 4** | Cross-Modal Alignment & MRS | **COMPLETE** | 9/9 checks passed (see below) |
| **Phase 5** | Graph Attribution & Entities | **COMPLETE** | 10/10 checks passed (see below) |
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

---

## Phase 3 Gate Verification Evidence

Command executed: `make gate PHASE=3` / `scripts/gates/phase_3.sh`

```
================================================================================
Project VIGIL - Gate 3 Verification (Social Intelligence & Hype Scoring)
================================================================================

| ID         | Check Description                             | Status | Detail                         |
|------------|-----------------------------------------------|--------|--------------------------------|
| P3-G0      | Core infra & services healthy                 | PASS   | Timescale, Neo4j, Redis, Redpanda |
| P3-G1      | Non-public visibility rejected (DLQ)          | PASS   | Reason VISIBILITY_NOT_PERMITTED |
| P3-G2      | LLM timeout & concurrency bounds              | PASS   | Timeout 2.0s & concurrency 8   |
| P3-G3      | HMAC pseudonymization (zero raw handles)      | PASS   | Zero raw handles/IDs stored    |
| AC-SOC-01  | Ticker F1 & CTA macro-F1 on corpus            | PASS   | Fallback >=0.85/0.70, LLM >=0.92/0.80 |
| AC-SOC-02  | Offline pipeline with FALLBACK_RULES          | PASS   | ANTHROPIC_API_KEY empty mode verified |
| AC-SOC-03  | pump_dump_ring_01 HYPE_BURST within 60s       | PASS   | Emitted within 27.0s <= 60s    |
| P3-TEST    | social_intel unit test suite coverage >= 80%  | PASS   | Coverage meets >= 80% threshold |
| P3-LINT    | Ruff and Mypy strict clean                    | PASS   | All files typed and lint-free  |
| P3-REPORT  | reports/social_eval.md generated and non-empty | PASS   | Social evaluation report ready |

================================================================================
GATE 3 RESULT: PASS (10/10 checks passed)
================================================================================
```

---

## Phase 3 Handoff Block

1. **Evaluation Metrics & Operating Modes (`reports/social_eval.md`):**
   - **Corpus Provenance:** Synthetic labeled corpus draft (`datasets/data/social_labeled_v1.draft.jsonl`, 504 rows) covering English and Hinglish across all 6 CTA classes and target tickers.
   - **`FALLBACK_RULES` Mode:** Ticker F1 = **0.9935** (target ≥ 0.85), CTA Macro-F1 = **0.8642** (target ≥ 0.70). Fully offline capable using Unicode NFKC normalization, cashtag/alias resolution, lexicon matching (`config/cta_lexicon.yaml`), and target price extraction.
   - **`LLM` Mode:** Ticker F1 = **0.9935** (target ≥ 0.92), CTA Macro-F1 = **1.0000** (target ≥ 0.80). Refines signals with bounded concurrency (`LLM_MAX_CONCURRENCY=8`) and timeout (`LLM_TIMEOUT_S=2.0`).

2. **Hype Scorer Calibration & Weights (`config/hype_weights.yaml`):**
   - **Formula Components:**
     - $f_{\text{rate}}$: Message arrival rate z-score vs 1-hour EWMA baseline ($\alpha=0.002$ per 5s step, $\sigma_{\min}=0.5$).
     - $f_{\text{auth}}$: Unique author count z-score in 60s sliding window.
     - $f_{\text{cta}}$: Non-neutral CTA confidence sum / $N$.
     - $f_{\text{dup}}$: Ratio of messages in MinHash-LSH near-duplicate clusters of size $\ge 3$.
     - $f_{\text{urg}}$: Average urgency score.
     - $f_{\text{xch}}$: Cross-channel spread factor $\min(1.0, (\text{channels} - 1) / 3.0)$.
   - **Weights:** $f_{\text{rate}}=0.25, f_{\text{auth}}=0.15, f_{\text{cta}}=0.20, f_{\text{dup}}=0.15, f_{\text{urg}}=0.10, f_{\text{xch}}=0.15$.
   - **Small Sample Guardrail:** If $N < 5$, hype score is strictly capped at $\le 20.0$.
   - **Anomaly Thresholds:** `HYPE_BURST` triggers when $\text{hype\_score} \ge 70.0$ continuously for $\ge 30.0$s; `NEAR_DUPLICATE_CAMPAIGN` triggers on clusters with $\ge 5$ messages, $\ge 3$ authors, $\ge 2$ channels within 5 min.

3. **Data Plane & Compliance Invariants Verified:**
   - **Visibility Gate (`P3-G1`):** Non-public or unlawful messages are rejected to `dlq.social` with diagnostic reason `VISIBILITY_NOT_PERMITTED`.
   - **Zero Raw PII (`P3-G3`):** HMAC-SHA256 pseudonymization converts all `author_id` and `message_id` into 22-character base64url tokens using keyed pepper before persistence or publication.
   - **AC-SOC-03 Verified:** In `pump_dump_ring_01`, `HYPE_BURST` anomaly on `ZENITHSME` is emitted within 27.0 seconds of the first coordinated pump message (comfortably beating the $\le 60$s requirement).
   - **Code Quality (`P3-TEST`, `P3-LINT`):** 85% test coverage on `social_intel`, 0 ruff lint errors, and 100% strict mypy compliance across all 73 source files.




---

## Phase 4 Gate Verification Evidence

Command executed: `scripts/gates/phase_4.sh`

```
================================================================================
Project VIGIL - Gate 4 Verification (Cross-Modal Alignment & MRS)
================================================================================

| ID         | Check Description                                  | Status | Detail                                   |
|------------|----------------------------------------------------|--------|------------------------------------------|
| P4-LINT    | Ruff lint clean across common & alignment_engine    | PASS   | 0 lint errors                            |
| P4-MYPY    | Mypy strict clean                                  | PASS   | 30 source files typed & clean            |
| P4-G3      | MRS component bounds in [0,1], weights sum to 1.00  | PASS   | 6/6 unit tests passed                    |
| P4-G1      | Deterministic p-value and lag given same inputs     | PASS   | Seeded circular block-shuffle PRNG       |
| P4-G2      | 30-s watermark preserves near-boundary late events  | PASS   | 4/4 integration tests passed             |
| AC-ALN-01  | Cross-modal alignment detected for ZENITHSME       | PASS   | best_lag_s > 0 (social leads, mean 150s) |
| AC-ALN-02  | baseline_01 false-positive control (seeds 1-5)      | PASS   | 0 false positive cases across 5 seeds    |
| AC-ALN-03  | MRS at dump start substantially exceeds baseline   | PASS   | 68.05 vs 4.65 (14.63x ratio)             |
| AC-ALN-04  | reports/alignment_eval.md generated & non-empty    | PASS   | ROC sweep & operating point committed    |

================================================================================
GATE 4 RESULT: PASS (9/9 checks passed)
================================================================================
```

---

## Phase 4 Handoff Block

1. **Operating Thresholds & Selection Rationale (`reports/alignment_eval.md`):**
   - **Significance Threshold:** $p < 0.01$ via circular block shuffle ($B=500$, block length 60s) with deterministic seed $(symbol, window\_id)$.
   - **XCorr Peak Threshold:** $\rho_{\text{peak}} \ge 0.30$ computed via FFT normalized cross-correlation ($\tau \in [-120, +1800]$s) on standardized series.
   - **Lag Direction:** $\text{best\_lag\_s} > 0$ strictly enforces that social hype leads market telemetry.
   - **Performance on Scenarios:**
     - `pump_dump_ring_01` (Seeds 1–5): 100% recall (5/5) with measured lag $\approx 150$s ($\pm 15$s), matching simulator ring reaction lag.
     - `baseline_01` (Seeds 1–5): 0 false positives ($p \ge 0.01$ or $\rho_{\text{peak}} < 0.30$).
     - Overall Precision = 1.0000, Recall = 1.0000, F1 = 1.0000.

2. **Event Fast-Path Bypass (`P4-T04`):**
   - Detects `HYPE_BURST` followed by `VOLUME_SPIKE` or `PRICE_JUMP` on the same ticker within $0 < \Delta t \le 900$s (15 minutes).
   - Fast-path qualifies immediately without requiring the full permutation test run, ensuring latency $\le 1$ second on confirmed coordinated attacks.

3. **Manipulation Risk Score (MRS) Calibration (`ARCHITECTURE.md §7.4`):**
   - Formula:
     $$\text{MRS} = 100 \times \left(0.30 \frac{\text{hype}}{100} + 0.25 \min\left(1, \frac{z_{\text{vol}}}{10}\right) + 0.15 \cdot \text{align} + 0.15 \cdot \text{ring} + 0.10 \cdot \text{price} + 0.05 \cdot \text{micro}\right)$$
   - Weights strictly sum to $1.00$, and all components are bounded in $[0, 1]$.
   - **Demo Scenario Sample Values (`pump_dump_ring_01`):**
     - Baseline ($t=0$s): $\text{MRS} = 4.65 / 100$.
     - Dump Start ($t=1140$s): $\text{MRS} = 68.05 / 100$ ($14.63\times$ escalation).
   - Persisted every minute into TimescaleDB `vigil.mrs_1m` and cached in Redis `mrs:{symbol}` with TTL 120s.

4. **Triggers & Downstream Handoff (`case.trigger` and `anomaly.fused`):**
   - Verified publishing of `CROSS_MODAL_ALIGNMENT` `AnomalyEvent` to Kafka topic `anomaly.fused`.
   - Verified publication of `CaseTrigger` payload to Kafka topic `case.trigger`.
   - Redis set `watchlist:symbols` automatically updated with elevated tickers for Phase 5 graph attribution and Phase 6 LangGraph case orchestration.

---

## Phase 5 Gate Verification Evidence

Command executed: `make gate PHASE=5` / `scripts/gates/phase_5.sh`

```
================================================================================
Project VIGIL - Gate 5 Verification (Graph Attribution, Rings & Feedback)
================================================================================

| ID         | Check Description                             | Status | Detail                         |
|------------|-----------------------------------------------|--------|--------------------------------|
| P5-G0      | Core infra & services healthy                 | PASS   | Timescale, Neo4j, Redis, Redpanda |
| P5-G1      | Feedback veto prevents recreation on re-run   | PASS   | Veto persistent across runs    |
| P5-G2      | Links < 0.60 never appear in findings         | PASS   | Leads segregated from findings |
| P5-G3      | Neo4j targeted chaos outage resilience        | PASS   | Outage handled & stack recovered |
| AC-GRA-01  | pump_dump_ring_01 recovery >= 18/20, prec >= 0.9 | PASS   | 20/20 recovered, prec 1.000    |
| AC-GRA-02  | Injected cycles found; baseline 0 cycles      | PASS   | Cycles lengths 2-5 identified  |
| AC-GRA-03  | Graph API export p95 < 800 ms (N=100)         | PASS   | p95 23.84 ms < 800 ms          |
| P5-TEST    | attribution unit test coverage >= 80%         | PASS   | Coverage meets >= 80% threshold |
| P5-LINT    | Ruff and Mypy strict clean                    | PASS   | 85 files typed and lint-free   |
| P5-REPORT  | reports/graph_eval.md generated & non-empty   | PASS   | Graph evaluation report ready  |

================================================================================
GATE 5 RESULT: PASS (10/10 checks passed)
================================================================================
```

---

## Phase 5 Handoff Block

1. **8 Link Methods & Weights Calibration (`config/attribution_weights.yaml`):**
   - Implemented in `services/agents/attribution/src/attribution/link_methods.py`:
     - `SHARED_KYC` (weight 0.35): Shared PAN, Aadhaar hash, bank account, email, or mobile.
     - `SHARED_DEVICE` (weight 0.25): Exact browser/hardware device fingerprint match.
     - `CIRCULAR_CYCLE` (weight 0.20): Directed trade cycle of length 2–6 with volume matching within 5%.
     - `SYNCHRONIZED_ORDERS` (weight 0.15): Orders placed in same 500 ms bin with Poisson tail $p < 0.01$.
     - `SHARED_NETWORK` (weight 0.10): Shared /24 subnet or ASN.
     - `LATENCY_SIGNATURE` (weight 0.08): Order submission time delta variance $\sigma < 5$ ms.
     - `REACTION_LATENCY` (weight 0.08): Statistically significant reaction time to social pump alerts (Mann-Whitney U $p < 0.01$).
     - `BROKER_PATHWAY` (weight 0.05): Same broker branch and sub-broker routing tag.

2. **Noisy-OR Confidence & Guardrail G-2 Enforcement (`confidence.py`):**
   - Pairwise confidence:
     $$\text{conf}_{ij} = 1 - \prod_{m \in M} (1 - w_m \cdot s_{m, ij})$$
   - **Guardrail G-2 Enforced:** Links with $\text{conf}_{ij} < 0.60$ are strictly classified as `leads` (`is_finding=False`) and NEVER appear in case findings or ring score calculation. Links with $\text{conf}_{ij} \ge 0.60$ are promoted to `findings` (`is_finding=True`).
   - Cluster Ring Score formula:
     $$\text{ring\_score} = 0.40 \cdot \overline{\text{conf}} + 0.30 \cdot \text{density} + 0.30 \cdot \min\left(1.0, \frac{V_{\text{internal}}}{V_{\text{total}}}\right)$$

3. **Ground-Truth Evaluation Summary (`reports/graph_eval.md`):**
   - **`pump_dump_ring_01`:** Recovered **20/20** ground-truth ring accounts (100% recall, target $\ge 18/20$). Exact precision is **1.000** (target $\ge 0.90$). Entity cluster ring score is **0.988**.
   - **`baseline_01`:** Exactly **0** cycles detected. 0 entity clusters meeting the ring score threshold ($\max = 0.354 \ll 0.60$).
   - Verified via `scripts/eval_graph.py` and `tests/integration/test_cycles.py`.

4. **Cycle & Community Detection Engines (`cycles.py`, `community.py`):**
   - `CycleDetector`: Streaming DFS cycle detection on multigraph edges for wash cycles of lengths 2–6.
   - `CommunityDetector`: Graph clustering using NetworkX Weakly Connected Components (WCC) and Louvain modularity refinement for large subgraphs ($>40$ nodes), ensuring deterministic execution without requiring proprietary Neo4j GDS enterprise licenses.

5. **Investigator Feedback Loop & Durability (`P5-G1`):**
   - `CONFIRM`: Investigator endorsement boosts link confidence to $\ge 0.95$ and pins it to the case graph.
   - `REJECT`: Investigator rejection stores a persistent bidirectional veto in Neo4j (`Veto` node and `VETOED_IN` relationship) and Redis key `veto:{case_id}:{acc_a}:{acc_b}`.
   - Verified that subsequent attribution re-runs over identical trading data strictly suppress vetoed links from being recreated.

6. **Graph API Export & Performance (`AC-GRA-03`):**
   - Cytoscape JSON export endpoint `GET /api/v1/cases/{case_id}/graph` tested over 100 consecutive requests:
     - p95 latency = **23.84 ms** (comfortably beating the PRD requirement of p95 $< 800$ ms).
   - Supports parameter filtering by `max_nodes` and `min_conf`.

