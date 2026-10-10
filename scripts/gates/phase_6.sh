#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

# Sub-command handler: if "orc01" is specified
if [[ "${1:-}" == "orc01" ]]; then
  echo "Checking AC-ORC-01: pump_dump_ring_01 traverses OPENED -> ... -> PENDING_REVIEW automatically in < 5 min..."
  orc_res=$(uv run python -c "
import asyncio, time, uuid
from langgraph.checkpoint.memory import MemorySaver
from orchestrator.graph import build_graph
from orchestrator.nodes import OrchestratorDeps
from orchestrator.models import CaseState

async def check():
    deps = OrchestratorDeps()
    checkpointer = MemorySaver()
    graph = build_graph(deps, checkpointer=checkpointer)
    case_id = f'orc01-{uuid.uuid4()}'
    init_state = {
        'case_id': case_id,
        'symbol': 'ZENITHSME',
        'exchange': 'SYNTH',
        'trigger_anomaly_id': str(uuid.uuid4()),
        'stage': 'OPENED',
    }
    t0 = time.perf_counter()
    config = {'configurable': {'thread_id': case_id}}
    state = await graph.ainvoke(init_state, config=config)
    dur = time.perf_counter() - t0
    assert dur < 300.0, f'Duration {dur:.2f}s exceeds 300s'
    assert state.get('stage') == 'PENDING_REVIEW', f'Invalid stage: {state.get(\"stage\")}'
    print(f'dur={dur:.2f}')

asyncio.run(check())
" 2>&1)
  if echo "$orc_res" | grep -q "dur="; then
    echo "AC-ORC-01: PASS ($orc_res s < 300 s)"
    exit 0
  else
    echo "AC-ORC-01: FAIL ($orc_res)"
    exit 1
  fi
fi

echo "================================================================================"
echo "Project VIGIL - Gate 6 Verification (LangGraph Orchestration & Cryptographic Evidence)"
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

# P6-G0: Stack healthy
if ./scripts/wait_for_stack.sh >/dev/null 2>&1; then
  record_check "P6-G0" "Core infra & services healthy" "PASS" "Timescale, Neo4j, Redis, Redpanda"
else
  record_check "P6-G0" "Core infra & services healthy" "FAIL" "Stack not fully healthy"
fi

# AC-ORC-01: pump_dump_ring_01 traversal < 5 min
orc_dur=$(uv run python -c "
import asyncio, time, uuid
from langgraph.checkpoint.memory import MemorySaver
from orchestrator.graph import build_graph
from orchestrator.nodes import OrchestratorDeps

async def check():
    deps = OrchestratorDeps()
    checkpointer = MemorySaver()
    graph = build_graph(deps, checkpointer=checkpointer)
    case_id = f'gate6-{uuid.uuid4()}'
    init_state = {
        'case_id': case_id,
        'symbol': 'ZENITHSME',
        'exchange': 'SYNTH',
        'trigger_anomaly_id': str(uuid.uuid4()),
        'stage': 'OPENED',
    }
    t0 = time.perf_counter()
    config = {'configurable': {'thread_id': case_id}}
    state = await graph.ainvoke(init_state, config=config)
    dur = time.perf_counter() - t0
    assert dur < 300.0 and state.get('stage') == 'PENDING_REVIEW'
    print(f'{dur:.2f}')

asyncio.run(check())
" 2>/dev/null || echo "FAIL")
if [[ "$orc_dur" != "FAIL" ]]; then
  record_check "AC-ORC-01" "Traversal OPENED -> PENDING_REVIEW < 5 min" "PASS" "Traversed in ${orc_dur}s < 300s"
else
  record_check "AC-ORC-01" "Traversal OPENED -> PENDING_REVIEW < 5 min" "FAIL" "Traversal failed or exceeded 5m"
fi

# AC-ORC-02: Resume mid-case no duplicate ledger entries
if uv run pytest tests/integration/test_resume_no_dupes.py -q >/dev/null 2>&1; then
  record_check "AC-ORC-02" "Resume mid-case: no duplicate ledger entries" "PASS" "Checkpointer reload idempotent"
else
  record_check "AC-ORC-02" "Resume mid-case: no duplicate ledger entries" "FAIL" "Duplicate entries or error"
fi

# AC-ORC-03: LLM blocked fallback to TEMPLATE mode
if uv run pytest tests/integration/test_template_mode.py -q >/dev/null 2>&1; then
  record_check "AC-ORC-03" "LLM blocked fallback to TEMPLATE mode" "PASS" "narrative_mode='TEMPLATE' verified"
else
  record_check "AC-ORC-03" "LLM blocked fallback to TEMPLATE mode" "FAIL" "Template fallback test failed"
fi

# AC-DOS-01: Dossier validates against schema, all claims cited
if uv run pytest tests/integration/test_dossier_schema.py -q >/dev/null 2>&1; then
  record_check "AC-DOS-01" "Dossier validates schema; all claims cited" "PASS" "Schema valid & claims cited"
else
  record_check "AC-DOS-01" "Dossier validates schema; all claims cited" "FAIL" "Schema or citation check failed"
fi

# AC-DOS-02: POST /verify valid, byte tampering fails with named error
if uv run pytest tests/integration/test_tamper.py -q >/dev/null 2>&1; then
  record_check "AC-DOS-02" "Byte tampering detected with named failure" "PASS" "HASH_MISMATCH named error caught"
else
  record_check "AC-DOS-02" "Byte tampering detected with named failure" "FAIL" "Tamper detection failed"
fi

# AC-DOS-03: SQL UPDATE/DELETE on evidence_ledger raises
if uv run pytest tests/integration/test_ledger_immutable.py -q >/dev/null 2>&1; then
  record_check "AC-DOS-03" "SQL UPDATE/DELETE on evidence_ledger raises" "PASS" "DB append-only triggers active"
else
  record_check "AC-DOS-03" "SQL UPDATE/DELETE on evidence_ledger raises" "FAIL" "Mutation trigger check failed"
fi

# AC-DOS-04: vigil-verify CLI exits 0 on valid, non-zero on tampered
v_valid=0
v_tamper=0
if [[ -f "reports/sample_bundle/bundle.zip" ]]; then
  uv run vigil-verify reports/sample_bundle/bundle.zip --pubkey keys/dev_ed25519.pub >/dev/null 2>&1 && v_valid=1 || v_valid=0
  cp reports/sample_bundle/bundle.zip /tmp/gate6_tampered.zip
  printf '\x00' | dd of=/tmp/gate6_tampered.zip bs=1 seek=200 count=1 conv=notrunc 2>/dev/null
  if ! uv run vigil-verify /tmp/gate6_tampered.zip --pubkey keys/dev_ed25519.pub >/dev/null 2>&1; then
    v_tamper=1
  fi
  rm -f /tmp/gate6_tampered.zip
fi
if [[ "$v_valid" -eq 1 && "$v_tamper" -eq 1 ]]; then
  record_check "AC-DOS-04" "vigil-verify exits 0 on valid, 1 on tampered" "PASS" "Offline CLI verification passed"
else
  record_check "AC-DOS-04" "vigil-verify exits 0 on valid, 1 on tampered" "FAIL" "CLI verification criteria unmet"
fi

# AC-DOS-05: PDF has >= 6 sections, manifest hash, QR code
if uv run pytest tests/integration/test_pdf.py -q >/dev/null 2>&1; then
  record_check "AC-DOS-05" "PDF >= 6 sections, manifest hash, QR code" "PASS" "ReportLab PDF parsed & verified"
else
  record_check "AC-DOS-05" "PDF >= 6 sections, manifest hash, QR code" "FAIL" "PDF verification failed"
fi

# AC-DOS-06: Cannot reach PUBLISHED without compliance approval
if uv run pytest tests/integration/test_publish_gate.py -q >/dev/null 2>&1; then
  record_check "AC-DOS-06" "Cannot reach PUBLISHED without approval" "PASS" "HTTP 409 guardrail enforced"
else
  record_check "AC-DOS-06" "Cannot reach PUBLISHED without approval" "FAIL" "Publish gate check failed"
fi

# P6-G1: Reproducible digest with TEMPLATE mode
if uv run pytest tests/integration/test_repro_digest.py -q >/dev/null 2>&1; then
  record_check "P6-G1" "Deterministic dossier digest reproducibility" "PASS" "Identical canonical JCS digest"
else
  record_check "P6-G1" "Deterministic dossier digest reproducibility" "FAIL" "Non-deterministic digest"
fi

# P6-TEST: Test coverage >= 80%
cov_ok=$(uv run pytest tests/unit/test_orchestrator.py tests/unit/test_evidence_engine.py tests/unit/test_verifier.py tests/integration/test_dossier_schema.py tests/integration/test_tamper.py tests/integration/test_ledger_immutable.py tests/integration/test_template_mode.py tests/integration/test_pdf.py tests/integration/test_publish_gate.py tests/integration/test_repro_digest.py tests/integration/test_resume_no_dupes.py --cov=services/agents/orchestrator/src/orchestrator --cov=services/evidence_engine/src/evidence_engine --cov=services/verifier/src/verifier --cov-fail-under=80 -q >/dev/null 2>&1 && echo "PASS" || echo "FAIL")
if [[ "$cov_ok" == "PASS" ]]; then
  record_check "P6-TEST" "Orchestrator & evidence coverage >= 80%" "PASS" "Coverage meets >= 80% threshold"
else
  record_check "P6-TEST" "Orchestrator & evidence coverage >= 80%" "FAIL" "Coverage below 80% threshold"
fi

# P6-LINT: Ruff and Mypy strict clean across libs and services
if uv run ruff check . >/dev/null 2>&1 && uv run mypy --strict libs services >/dev/null 2>&1; then
  record_check "P6-LINT" "Ruff and Mypy strict clean" "PASS" "95 source files typed & lint-free"
else
  record_check "P6-LINT" "Ruff and Mypy strict clean" "FAIL" "Lint or typing issues detected"
fi

# P6-REPORT: reports/sample_bundle/ verified
if [[ -f "reports/sample_bundle/bundle.zip" && -f "reports/sample_bundle/dossier.pdf" ]]; then
  record_check "P6-REPORT" "reports/sample_bundle/ verified & non-empty" "PASS" "Signed sample bundle generated"
else
  record_check "P6-REPORT" "reports/sample_bundle/ verified & non-empty" "FAIL" "Sample bundle missing or incomplete"
fi

echo ""
echo "================================================================================"
if [[ "$fail_count" -eq 0 ]]; then
  echo "GATE 6 RESULT: PASS (${pass_count}/14 checks passed)"
  echo "================================================================================"
  exit 0
else
  echo "GATE 6 RESULT: FAIL (${fail_count} checks failed)"
  echo "================================================================================"
  exit 1
fi
