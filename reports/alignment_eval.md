# Cross-Modal Alignment & MRS Calibration Report

## 1. Operating Point Selection

- **Significance Threshold (p-value)**: `p < 0.01`
- **Normalized Cross-Correlation Threshold**: `xcorr_peak >= 0.30`
- **Lag Direction**: `best_lag_s > 0` (Social hype leads market activity)
- **Precision**: `1.0000` (5/5)
- **Recall**: `1.0000` (5/5)
- **F1-Score**: `1.0000`
- **False Positives**: `0` on baseline_01 (seeds 1-5)

## 2. Threshold Sweep (ROC / Precision-Recall Grid)

| p_thr | xcorr_thr | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| 0.001 | 0.2 | 0 | 0 | 5 | 5 | 1.000 | 0.000 | 0.000 |
| 0.001 | 0.3 | 0 | 0 | 5 | 5 | 1.000 | 0.000 | 0.000 |
| 0.001 | 0.4 | 0 | 0 | 5 | 5 | 1.000 | 0.000 | 0.000 |
| 0.001 | 0.5 | 0 | 0 | 5 | 5 | 1.000 | 0.000 | 0.000 |
| 0.005 | 0.2 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.005 | 0.3 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.005 | 0.4 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.005 | 0.5 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.01 | 0.2 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.01 | 0.3 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.01 | 0.4 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.01 | 0.5 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.02 | 0.2 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.02 | 0.3 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.02 | 0.4 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.02 | 0.5 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.05 | 0.2 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.05 | 0.3 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.05 | 0.4 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |
| 0.05 | 0.5 | 5 | 0 | 0 | 5 | 1.000 | 1.000 | 1.000 |

## 3. MRS Calibration (Demo Scenario: pump_dump_ring_01)

- **Baseline MRS (t=0s)**: `4.65` / 100
- **Dump Start MRS (t=1140s)**: `68.05` / 100
- **Dynamic Range Ratio**: `14.63x`

## 4. Verification Notes

- Determinism confirmed across runs (P4-G1).
- 30-s watermark properly preserves near-boundary late events (P4-G2).
- MRS component bounds [0, 1] strictly preserved and weights sum to 1.00 (P4-G3).
