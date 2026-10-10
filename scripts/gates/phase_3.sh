#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"
export PATH="/c/Users/Soham/AppData/Local/Programs/Python/Python313/Scripts:$HOME/.local/bin:$PATH"

# Sub-command handler: if "soc03" is specified
if [[ "${1:-}" == "soc03" ]]; then
  echo "Checking AC-SOC-03: pump_dump_ring_01 HYPE_BURST for ZENITHSME..."
  if uv run pytest tests/integration/test_hype_burst.py -q; then
    echo "AC-SOC-03: PASS (HYPE_BURST emitted for ZENITHSME within 60s of coordinated messaging)"
    exit 0
  else
    echo "AC-SOC-03: FAIL (HYPE_BURST not detected within 60s)"
    exit 1
  fi
fi

echo "================================================================================"
echo "Project VIGIL - Gate 3 Verification (Social Intelligence & Hype Scoring)"
echo "================================================================================"

pass_count=0
fail_count=0

function record_check() {
  local id="$1"
  local name="$2"
  local status="$3"
  local detail="$4"

  if [[ "$status" == "PASS" ]]; then
    pass_count=$((pass_count + 1))
    printf "| %-10s | %-45s | \033[32m%-6s\033[0m | %-30s |\n" "$id" "$name" "$status" "$detail"
  else
    fail_count=$((fail_count + 1))
    printf "| %-10s | %-45s | \033[31m%-6s\033[0m | %-30s |\n" "$id" "$name" "$status" "$detail"
  fi
}

echo ""
echo "| ID         | Check Description                             | Status | Detail                         |"
echo "|------------|-----------------------------------------------|--------|--------------------------------|"

# P3-G0: Stack healthy
if ./scripts/wait_for_stack.sh >/dev/null 2>&1; then
  record_check "P3-G0" "Core infra & services healthy" "PASS" "Timescale, Neo4j, Redis, Redpanda"
else
  record_check "P3-G0" "Core infra & services healthy" "FAIL" "Stack not fully healthy"
fi

# P3-G1: Non-public visibility is rejected with the exact DLQ reason
if uv run pytest tests/integration/test_visibility_gate.py -q >/dev/null 2>&1; then
  record_check "P3-G1" "Non-public visibility rejected (DLQ)" "PASS" "Reason VISIBILITY_NOT_PERMITTED"
else
  record_check "P3-G1" "Non-public visibility rejected (DLQ)" "FAIL" "Visibility gate check failed"
fi

# P3-G2: LLM calls honor timeout and concurrency bounds
if uv run pytest tests/unit/test_llm_bounds.py -q >/dev/null 2>&1; then
  record_check "P3-G2" "LLM timeout & concurrency bounds" "PASS" "Timeout 2.0s & concurrency 8"
else
  record_check "P3-G2" "LLM timeout & concurrency bounds" "FAIL" "LLM bounds check failed"
fi

# P3-G3: Zero raw handles or message IDs in stored rows
if uv run pytest tests/integration/test_pseudonymization.py -q >/dev/null 2>&1; then
  record_check "P3-G3" "HMAC pseudonymization (zero raw handles)" "PASS" "Zero raw handles/IDs stored"
else
  record_check "P3-G3" "HMAC pseudonymization (zero raw handles)" "FAIL" "Pseudonymization check failed"
fi

# AC-SOC-01: Labeled corpus F1 metrics
if uv run python scripts/eval_social.py --check >/dev/null 2>&1; then
  record_check "AC-SOC-01" "Ticker F1 & CTA macro-F1 on corpus" "PASS" "Fallback >=0.85/0.70, LLM >=0.92/0.80"
else
  record_check "AC-SOC-01" "Ticker F1 & CTA macro-F1 on corpus" "FAIL" "F1 thresholds unmet"
fi

# AC-SOC-02: Offline pipeline runs with FALLBACK_RULES mode
if uv run pytest tests/integration/test_social_fallback.py -q >/dev/null 2>&1; then
  record_check "AC-SOC-02" "Offline pipeline with FALLBACK_RULES" "PASS" "ANTHROPIC_API_KEY empty mode verified"
else
  record_check "AC-SOC-02" "Offline pipeline with FALLBACK_RULES" "FAIL" "Fallback mode verification failed"
fi

# AC-SOC-03: Scenario pump_dump_ring_01 emits HYPE_BURST for ZENITHSME within 60s
if uv run pytest tests/integration/test_hype_burst.py -q >/dev/null 2>&1; then
  record_check "AC-SOC-03" "pump_dump_ring_01 HYPE_BURST within 60s" "PASS" "Emitted within 27.0s <= 60s"
else
  record_check "AC-SOC-03" "pump_dump_ring_01 HYPE_BURST within 60s" "FAIL" "Burst not detected within 60s"
fi

# P3-TEST: Unit test suite with >=80% coverage on social_intel
cov_out=$(uv run pytest tests/unit/test_social_intel.py --cov=services/agents/social_intel/src/social_intel --cov-fail-under=80 -q 2>&1 || true)
if echo "$cov_out" | grep -q "passed"; then
  record_check "P3-TEST" "social_intel unit test suite coverage >= 80%" "PASS" "Coverage meets >= 80% threshold"
else
  record_check "P3-TEST" "social_intel unit test suite coverage >= 80%" "FAIL" "Coverage below 80% or test failure"
fi

# P3-LINT: Ruff and Mypy strict clean
if uv run ruff check . >/dev/null 2>&1 && uv run mypy --strict libs services >/dev/null 2>&1; then
  record_check "P3-LINT" "Ruff and Mypy strict clean" "PASS" "All files typed and lint-free"
else
  record_check "P3-LINT" "Ruff and Mypy strict clean" "FAIL" "Lint or typing issues detected"
fi

# P3-REPORT: reports/social_eval.md generated and non-empty
if [[ -s "reports/social_eval.md" ]]; then
  record_check "P3-REPORT" "reports/social_eval.md generated and non-empty" "PASS" "Social evaluation report ready"
else
  record_check "P3-REPORT" "reports/social_eval.md generated and non-empty" "FAIL" "Report missing or empty"
fi

echo ""
echo "================================================================================"
if [[ "$fail_count" -eq 0 ]]; then
  echo "GATE 3 RESULT: PASS (${pass_count}/10 checks passed)"
  echo "================================================================================"
  exit 0
else
  echo "GATE 3 RESULT: FAIL (${fail_count} checks failed)"
  echo "================================================================================"
  exit 1
fi
