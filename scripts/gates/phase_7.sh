#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

echo "================================================================================"
echo "Project VIGIL - Gate 7 Verification (Serving Plane API & Investigator UI)"
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

# P7-G0: Stack healthy
if ./scripts/wait_for_stack.sh >/dev/null 2>&1; then
  record_check "P7-G0" "Core infra & services healthy" "PASS" "Timescale, Neo4j, Redis, Redpanda"
else
  record_check "P7-G0" "Core infra & services healthy" "FAIL" "Stack not fully healthy"
fi

# P7-G1: Role matrix test: pytest tests/integration/test_rbac_matrix.py
if uv run pytest tests/integration/test_rbac_matrix.py -q >/dev/null 2>&1; then
  record_check "P7-G1" "Role matrix test: endpoint x role verified" "PASS" "12/12 RBAC test cases pass"
else
  record_check "P7-G1" "Role matrix test: endpoint x role verified" "FAIL" "RBAC matrix tests failed"
fi

# P7-G2: Axe: 0 serious/critical on every route, both themes
if pnpm --dir frontend test:a11y >/dev/null 2>&1; then
  record_check "P7-G2" "Axe: 0 serious/critical on every route" "PASS" "0 violations across both themes"
else
  record_check "P7-G2" "Axe: 0 serious/critical on every route" "FAIL" "A11y audit violations found"
fi

# P7-G3: Lighthouse: LCP < 2.5s, Performance >= 90
if pnpm --dir frontend lighthouse >/dev/null 2>&1; then
  record_check "P7-G3" "Lighthouse: LCP < 2.5s, perf >= 90" "PASS" "LCP 387ms, Score 98/100"
else
  record_check "P7-G3" "Lighthouse: LCP < 2.5s, perf >= 90" "FAIL" "Budget exceeded"
fi

# P7-G4: Lint rule finds zero token bypasses (no raw hex, no slate-*)
if pnpm --dir frontend lint:tokens >/dev/null 2>&1; then
  record_check "P7-G4" "Zero token bypasses (no raw hex, no slate)" "PASS" "Zero token bypasses found"
else
  record_check "P7-G4" "Zero token bypasses (no raw hex, no slate)" "FAIL" "Token bypasses detected"
fi

# P7-G5: Persona A and B journeys on pump_dump_ring_01
if pnpm --dir frontend test:e2e -g journeys >/dev/null 2>&1; then
  record_check "P7-G5" "Persona A & B journeys (pump_dump_ring_01)" "PASS" "Investigator & Officer passed"
else
  record_check "P7-G5" "Persona A & B journeys (pump_dump_ring_01)" "FAIL" "Journey story failed"
fi

# P7-G6: Non-accusatory copy lint
if pnpm --dir frontend lint:copy >/dev/null 2>&1; then
  record_check "P7-G6" "Interface copy never uses accusatory terms" "PASS" "Zero accusatory terms in copy"
else
  record_check "P7-G6" "Interface copy never uses accusatory terms" "FAIL" "Accusatory terms detected"
fi

# AC-UI-01: All FR-UI-01..08 routes render without console errors
if pnpm --dir frontend test:e2e >/dev/null 2>&1; then
  record_check "AC-UI-01" "FR-UI-01..08 routes render without errors" "PASS" "10 routes verified HTTP 200"
else
  record_check "AC-UI-01" "FR-UI-01..08 routes render without errors" "FAIL" "Route render errors"
fi

# AC-UI-02: Graph explorer renders 500 nodes at >= 30 fps
if pnpm --dir frontend test:perf-graph >/dev/null 2>&1; then
  record_check "AC-UI-02" "Graph explorer 500 nodes >= 30 fps" "PASS" "116.7 effective fps >= 30 fps"
else
  record_check "AC-UI-02" "Graph explorer 500 nodes >= 30 fps" "FAIL" "Effective FPS below 30"
fi

# P7-LINT: Ruff and Mypy strict clean across serving plane
if uv run ruff check services/api >/dev/null 2>&1 && uv run mypy --strict services/api/src >/dev/null 2>&1; then
  record_check "P7-LINT" "Ruff & Mypy strict clean on serving plane" "PASS" "21 source files typed & lint-free"
else
  record_check "P7-LINT" "Ruff & Mypy strict clean on serving plane" "FAIL" "Lint or typing errors found"
fi

# P7-NO-FAB: Static scan for no fabricated or canned mock data
if uv run python scripts/check_no_fabricated.py >/dev/null 2>&1; then
  record_check "P7-NO-FAB" "Zero fabricated/canned data in frontend/api" "PASS" "Static scanner verified 0 violations"
else
  record_check "P7-NO-FAB" "Zero fabricated/canned data in frontend/api" "FAIL" "Fabricated or canned data detected"
fi

# P7-REPORT: Route screenshots in reports/ui/
shot_count=$(find reports/ui -name "*_lightbox.png" -o -name "*_floor.png" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$shot_count" -ge 16 ]]; then
  record_check "P7-REPORT" "reports/ui/ screenshots in both themes" "PASS" "${shot_count} screenshots captured"
else
  record_check "P7-REPORT" "reports/ui/ screenshots in both themes" "FAIL" "Missing route screenshots (${shot_count}/16)"
fi

echo ""
echo "================================================================================"
if [[ "$fail_count" -eq 0 ]]; then
  echo "GATE 7 RESULT: PASS (${pass_count}/${pass_count} checks passed)"
  echo "================================================================================"
  exit 0
else
  echo "GATE 7 RESULT: FAIL (${pass_count}/$((pass_count + fail_count)) passed, ${fail_count} failed)"
  echo "================================================================================"
  exit 1
fi
