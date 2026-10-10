# Project VIGIL: Quantitative Telemetry Detector Evaluation Report (`QTA`)

**Generated At:** 2026-10-10 22:19:07 UTC
**Evaluated Seeds:** [1, 2, 3, 4, 5]
**Overall Gate Evaluation Status:** **PASS**

## 1. Executive Summary & Acceptance Criteria Verification

| Criterion | Scenario | Target Symbol | Metric Tested | Requirement | Observed Status | Result |
|---|---|---|---|---|---|---|
| **AC-QTA-01** | `baseline_01` | ZENITHSME | Volume Spike & Price Jump FP | Exactly 0 on target | 0 anomalies across seeds 1–5 | **PASS** |
| **AC-QTA-01** | `pump_dump_ring_01` | ZENITHSME | Volume Spike & Price Jump TP | Both detected on target | Both detected across seeds 1–5 | **PASS** |
| **AC-QTA-02** | `wash_ring_01` | ACMESYSTEMS | Wash Cycle Recall & Precision | Recall ≥ 0.90, Precision ≥ 0.80 | Recall: 96.0%, Precision: 100.0% | **PASS** |
| **AC-QTA-03** | `spoofing_01` | NOVAPHARMA | Spoofer Identification Recall | Recall ≥ 0.90 per spoofer | Recall: 100.0% (100% across seeds) | **PASS** |

---

## 2. Per-Scenario Evaluation Details

### 2.1 Scenario: `baseline_01` (False Positive Control)
Organic market flow across 40 symbols with ambient Poisson order flow and GBM asset drift.
| Seed | Target Symbol | Volume Spikes Detected | Price Jumps Detected | Status |
|---|---|---|---|---|
| Seed 1 | ZENITHSME | 0 | 0 | PASS |
| Seed 2 | ZENITHSME | 0 | 0 | PASS |
| Seed 3 | ZENITHSME | 0 | 0 | PASS |
| Seed 4 | ZENITHSME | 0 | 0 | PASS |
| Seed 5 | ZENITHSME | 0 | 0 | PASS |

### 2.2 Scenario: `pump_dump_ring_01` (Coordinated Pump & Dump)
Target symbol ZENITHSME undergoes coordinated accumulation, social-aligned volume spike, and rapid price jump.
| Seed | Target Symbol | Volume Spikes | Price Jumps | Status |
|---|---|---|---|---|
| Seed 1 | ZENITHSME | 1 | 5 | PASS |
| Seed 2 | ZENITHSME | 1 | 4 | PASS |
| Seed 3 | ZENITHSME | 1 | 5 | PASS |
| Seed 4 | ZENITHSME | 1 | 2 | PASS |
| Seed 5 | ZENITHSME | 1 | 4 | PASS |

### 2.3 Scenario: `wash_ring_01` (Multi-Hop Circular Wash Trading)
6 ring accounts execute pre-arranged matched volume cycles of lengths 2 through 5.
| Seed | Target Symbol | Injected Trades | Detected Trades | Cycle Anomalies | Recall | Precision | Status |
|---|---|---|---|---|---|---|---|
| Seed 1 | ACMESYSTEMS | 38 | 37 | 28 | 97.4% | 100.0% | PASS |
| Seed 2 | ACMESYSTEMS | 13 | 13 | 8 | 100.0% | 100.0% | PASS |
| Seed 3 | ACMESYSTEMS | 2 | 2 | 1 | 100.0% | 100.0% | PASS |
| Seed 4 | ACMESYSTEMS | 14 | 13 | 8 | 92.9% | 100.0% | PASS |
| Seed 5 | ACMESYSTEMS | 20 | 18 | 13 | 90.0% | 100.0% | PASS |

### 2.4 Scenario: `spoofing_01` (Order Book Layering & Fleeting Orders)
2 spoofer accounts layer 5 large buy orders below best bid, execute opposite sell trade, and cancel.
| Seed | Target Symbol | Injected Spoofers | Identified Spoofers | Total Layering Anomalies | Recall | Status |
|---|---|---|---|---|---|---|
| Seed 1 | NOVAPHARMA | 2 | 2 | 6 | 100.0% | PASS |
| Seed 2 | NOVAPHARMA | 2 | 2 | 6 | 100.0% | PASS |
| Seed 3 | NOVAPHARMA | 2 | 2 | 6 | 100.0% | PASS |
| Seed 4 | NOVAPHARMA | 2 | 2 | 6 | 100.0% | PASS |
| Seed 5 | NOVAPHARMA | 2 | 2 | 6 | 100.0% | PASS |

---

## 3. Active Detector Configuration & Thresholds Handoff

```yaml
version: "1.0.0"
tiers:
  micro:
    volume_spike: { z_thr: 4.0, k: 3 }
    price_jump: { sigma_thr: 5.0 }
  mid:
    volume_spike: { z_thr: 5.0, k: 3 }
    price_jump: { sigma_thr: 5.0 }
  large:
    volume_spike: { z_thr: 6.0, k: 4 }
    price_jump: { sigma_thr: 6.0 }

spread_depth:
  spread_mult: 3.0
  imbalance_thr: 0.7
  imbalance_hold_s: 10
  top_levels: 5

spoofing:
  window_ms: 2000
  min_orders: 5
  cancel_ratio: 0.9
  qty_mult: 5
  exec_ms: 1000

wash_cycle:
  cycle_window_s: 900
  qty_tol: 0.05
  price_tol: 0.005
  max_len: 5

sync_orders:
  bin_ms: 500
  min_accounts: 3
  min_bins: 3
  window_s: 600
  p_thr: 0.01

alignment:
  lags_s: [-120, 1800]
  block_s: 60
  shuffles: 500
  peak_thr: 0.5
  p_thr: 0.01
  max_lag_s: 900

hype:
  burst_score: 70
  burst_hold_s: 30
  window_s: 60
  step_s: 5
  min_msgs: 5

case:
  overlap_merge_ratio: 0.5
  watchlist_cooldown_min: 60
  min_conf_proceed: 0.40
  min_conf_no_loop: 0.60
  max_widen: 2
```

---

## 4. Architectural Invariants Verified
- **PRNG Determinism:** Simulator seeds generate byte-identical streams (`test_sim_determinism.py`).
- **Ingest DLQ Isolation:** Schema violations are routed to `dlq.market` (`test_dlq.py`).
- **Sequence Integrity:** Missing seq IDs emit `SEQ_GAP` health events (`test_seq_gap.py`).
- **Idempotent Storage:** Duplicate replay leaves TimescaleDB row count invariant (`test_idempotent_replay.py`).
- **Detection Coverage:** Quantitative Telemetry service achieves ≥ 90% unit test coverage.