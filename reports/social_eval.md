# Social Intelligence Evaluation Report (Phase 3)

## Executive Summary

- **Corpus**: `datasets/data/social_labeled_v1.draft.jsonl` (synthetic-draft, 504 rows)
- **Target Criteria (AC-SOC-01)**:
  - Fallback mode (`FALLBACK_RULES`): Ticker F1 ≥ 0.85, CTA Macro-F1 ≥ 0.70
  - LLM mode (`LLM`): Ticker F1 ≥ 0.92, CTA Macro-F1 ≥ 0.80

## Performance Metrics Summary

| Mode | Ticker Precision | Ticker Recall | Ticker F1 | CTA Macro-F1 | Status |
|---|---|---|---|---|---|
| `FALLBACK_RULES` | 100.00% | 98.70% | **0.9935** | **0.8642** | PASS |
| `LLM` | 100.00% | 98.70% | **0.9935** | **1.0000** | PASS |

## Detailed CTA Class Performance (`FALLBACK_RULES`)

| CTA Class | Precision | Recall | F1 Score | Support |
|---|---|---|---|---|
| `BUY_CALL` | 76.47% | 81.25% | 0.7879 | 112 |
| `HOLD_PUMP` | 84.62% | 100.00% | 0.9167 | 77 |
| `TARGET_PRICE` | 100.00% | 54.55% | 0.7059 | 77 |
| `EXIT_SIGNAL` | 100.00% | 100.00% | 1.0000 | 77 |
| `COORDINATION_TIMING` | 100.00% | 90.00% | 0.9474 | 70 |
| `NEUTRAL` | 75.00% | 92.31% | 0.8276 | 91 |

## Provenance & Edge Case Observations

1. **Corpus Provenance**: Synthetic-draft corpus generated from simulator templates, organic chatter patterns, and Hinglish Telegram/Discord pump channels.
2. **Hinglish Phrasing**: Rules correctly match Hinglish call idioms ('kharido', 'lelo', 'becho', 'niklo', 'dhamaka', 'circuit lagne wala hai').
3. **Ambiguity Handling**: Bare words that collide with standard vocabulary (e.g., 'ZEN', 'SOLAR') require corroborating financial keywords ('buy', 'stock', 'target', 'circuit') before resolution.
4. **LLM Refinement Bounds**: Honored with concurrency bound (`LLM_MAX_CONCURRENCY=8`) and timeout (`LLM_TIMEOUT_S=2.0`), falling back to `FALLBACK_RULES` on any failure.

