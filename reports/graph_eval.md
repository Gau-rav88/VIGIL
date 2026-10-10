# Project VIGIL: Cyber-Forensics Graph Attribution Evaluation Report (`GRA`)

**Generated At:** 2026-10-10 10:11:09 UTC
**Overall Gate Evaluation Status:** **PASS**

## 1. Acceptance Criteria Verification (`AC-GRA-01`, `AC-GRA-02`)

| Evaluation Metric | Target Threshold | Measured Result | Status |
|---|---|---|---|
| Ring Account Recovery | $\ge 18$ of 20 accounts | Mean: 20.0/20 | **PASS** |
| Entity Attribution Precision | $\ge 0.90$ | Mean: 1.000 | **PASS** |
| Entity Ring Score | $\ge 0.80$ | Mean: 0.988 | **PASS** |
| `baseline_01` False Rings | 0 cycles, score < 0.60 | 0 cycles, max score 0.354 | **PASS** |

## 2. Per-Seed Recovery Breakdown (`pump_dump_ring_01`)

| Seed | Ring Recovered | Precision | Recall | Ring Score | Cycles Found | Status |
|---|---|---|---|---|---|---|
| 1 | 20/20 | 1.000 | 1.000 | 0.988 | 34 | PASS |
| 2 | 20/20 | 1.000 | 1.000 | 0.988 | 36 | PASS |
| 3 | 20/20 | 1.000 | 1.000 | 0.988 | 51 | PASS |
| 4 | 20/20 | 1.000 | 1.000 | 0.988 | 25 | PASS |
| 5 | 20/20 | 1.000 | 1.000 | 0.988 | 32 | PASS |

## 3. Calibrated Attribution Weights (`config/attribution_weights.yaml`)

| Method | Weight | Evidence Basis |
|---|---|---|
| `SHARED_KYC` | 0.95 | Evidence strength $s \in [0, 1]$ mapped via noisy-OR |
| `SHARED_DEVICE` | 0.90 | Evidence strength $s \in [0, 1]$ mapped via noisy-OR |
| `CIRCULAR_CYCLE` | 0.85 | Evidence strength $s \in [0, 1]$ mapped via noisy-OR |
| `SYNCHRONIZED_ORDERS` | 0.70 | Evidence strength $s \in [0, 1]$ mapped via noisy-OR |
| `SHARED_NETWORK` | 0.60 | Evidence strength $s \in [0, 1]$ mapped via noisy-OR |
| `LATENCY_SIGNATURE` | 0.50 | Evidence strength $s \in [0, 1]$ mapped via noisy-OR |
| `REACTION_LATENCY` | 0.50 | Evidence strength $s \in [0, 1]$ mapped via noisy-OR |
| `BROKER_PATHWAY` | 0.40 | Evidence strength $s \in [0, 1]$ mapped via noisy-OR |

## 4. Key Architectural Guarantees Verified
- **PRD Guardrail G-2 (Probabilistic Attribution):** Links with confidence $< 0.60$ are strictly classified as inferred-low leads and excluded from findings.
- **P5-G1 (Investigator Feedback Veto):** Rejected links store persistent vetoes in Neo4j and Redis and are never recreated upon attribution re-run.
- **Degraded Mode Support:** Operates seamlessly via NetworkX in-memory graph when Neo4j is offline, maintaining 100% test coverage.

