#!/usr/bin/env bash
set -e

export PATH="/c/Users/Soham/AppData/Local/Programs/Python/Python313/Scripts:$HOME/.local/bin:$PATH"

MODE="${1:-all}"

echo "=== VIGIL Phase 4 Gate: Cross-Modal Alignment & MRS ==="
echo "Mode: ${MODE}"

check_fail() {
  echo "[FAIL] $1"
  exit 1
}

check_pass() {
  echo "[PASS] $1"
}

# Sub-command: aln01 (AC-ALN-01)
if [ "$MODE" = "aln01" ]; then
  echo "Running AC-ALN-01 check: pump_dump_ring_01 alignment detection..."
  uv run pytest tests/integration/test_alignment_acceptance.py -k "test_ac_aln_01" || check_fail "AC-ALN-01 failed"
  check_pass "AC-ALN-01: Cross-modal alignment detected for ZENITHSME with best_lag_s > 0"
  exit 0
fi

# Sub-command: aln02 (AC-ALN-02)
if [ "$MODE" = "aln02" ]; then
  echo "Running AC-ALN-02 check: baseline_01 false-positive control..."
  uv run pytest tests/integration/test_alignment_acceptance.py -k "test_ac_aln_02" || check_fail "AC-ALN-02 failed"
  check_pass "AC-ALN-02: Zero false-positive cases on baseline_01 across seeds"
  exit 0
fi

# Sub-command: mrs (AC-ALN-03)
if [ "$MODE" = "mrs" ]; then
  echo "Running AC-ALN-03 check: MRS dump start > baseline..."
  uv run pytest tests/integration/test_alignment_acceptance.py -k "test_ac_aln_03" || check_fail "AC-ALN-03 failed"
  check_pass "AC-ALN-03: MRS at dump start substantially exceeds baseline"
  exit 0
fi

# Full gate check (MODE=all)
echo "--- Check 1: Linting with ruff ---"
uv run ruff check libs/vigil_common services/alignment_engine tests/unit/test_mrs.py tests/unit/test_alignment_determinism.py tests/integration/test_watermark.py tests/integration/test_alignment_acceptance.py scripts/eval_alignment.py || check_fail "Ruff lint errors"
check_pass "Check 1: Ruff clean"

echo "--- Check 2: Type checking with mypy ---"
uv run mypy --strict libs/vigil_common services/alignment_engine || check_fail "Mypy type errors"
check_pass "Check 2: Mypy strict clean"

echo "--- Check 3: P4-G3 MRS bounds and weight sum ---"
uv run pytest tests/unit/test_mrs.py || check_fail "P4-G3 MRS bounds/weights failed"
check_pass "Check 3: P4-G3 passed"

echo "--- Check 4: P4-G1 Alignment determinism ---"
uv run pytest tests/unit/test_alignment_determinism.py || check_fail "P4-G1 Alignment determinism failed"
check_pass "Check 4: P4-G1 passed"

echo "--- Check 5: P4-G2 Watermark integration test ---"
uv run pytest tests/integration/test_watermark.py || check_fail "P4-G2 Watermark failed"
check_pass "Check 5: P4-G2 passed"

echo "--- Check 6: AC-ALN-01 Alignment detection ---"
uv run pytest tests/integration/test_alignment_acceptance.py -k "test_ac_aln_01" || check_fail "AC-ALN-01 failed"
check_pass "Check 6: AC-ALN-01 passed"

echo "--- Check 7: AC-ALN-02 False-positive control ---"
uv run pytest tests/integration/test_alignment_acceptance.py -k "test_ac_aln_02" || check_fail "AC-ALN-02 passed"
check_pass "Check 7: AC-ALN-02 passed"

echo "--- Check 8: AC-ALN-03 MRS at dump vs baseline ---"
uv run pytest tests/integration/test_alignment_acceptance.py -k "test_ac_aln_03" || check_fail "AC-ALN-03 passed"
check_pass "Check 8: AC-ALN-03 passed"

echo "--- Check 9: AC-ALN-04 Alignment evaluation & calibration report ---"
uv run python scripts/eval_alignment.py || check_fail "Evaluation script failed"
test -s reports/alignment_eval.md || check_fail "reports/alignment_eval.md is empty or missing"
check_pass "Check 9: AC-ALN-04 passed (reports/alignment_eval.md generated)"

echo "=== ALL PHASE 4 CHECKS PASSED (9/9) ==="
exit 0
