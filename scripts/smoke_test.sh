#!/usr/bin/env bash
set -euo pipefail

API_BASE=${API_BASE:-http://localhost:8001}
API=${API:-${API_BASE}/api/v1}
SIM=${SIM:-http://localhost:8090}

echo "================================================================================"
echo "Project VIGIL - End-to-End Pipeline Smoke Test"
echo "================================================================================"

echo "[1/9] Health and readiness check"
for s in healthz readyz; do
  STATUS_CODE=$(curl -fsS -o /dev/null -w "%{http_code}" "${API_BASE}/$s")
  if [ "$STATUS_CODE" -ne 200 ]; then
    echo "FAIL: ${API_BASE}/$s returned $STATUS_CODE"
    exit 1
  fi
done
echo "  -> healthz and readyz both returned HTTP 200"

echo "[2/9] Auth: dev token issuance and RBAC check"
TOKEN=$(curl -fsS -X POST "$API/auth/dev-token" -H 'content-type: application/json' -d '{"sub":"smoke-c","role":"compliance_officer"}' | jq -r .token)
if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "FAIL: Failed to acquire dev token"
  exit 1
fi
H=(-H "authorization: Bearer $TOKEN")

# Verify unauthenticated request returns 401
UNAUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/cases")
if [ "$UNAUTH_CODE" -ne 401 ]; then
  echo "FAIL: Unauthenticated request returned $UNAUTH_CODE instead of 401"
  exit 1
fi
echo "  -> Token issued, unauthenticated 401 verified"

echo "[3/9] Empty DB state assertion"
# Clean cases and evidence tables to start fresh
docker exec vigil-timescale-1 psql -U vigil -d vigil -c "DELETE FROM vigil.evidence_objects; DELETE FROM vigil.dossiers; DELETE FROM vigil.case_events; DELETE FROM vigil.cases;" >/dev/null 2>&1 || true

CASES_EMPTY=$(curl -fsS "${H[@]}" "$API/cases?limit=10" | jq '.items | length')
ANOMS_EMPTY=$(curl -fsS "${H[@]}" "$API/anomalies?limit=10" | jq '.items | length')
if [ "$CASES_EMPTY" -ne 0 ]; then
  echo "FAIL: Cases not empty on initial clean state ($CASES_EMPTY items)"
  exit 1
fi
echo "  -> Empty DB correctly returns 0 cases ($CASES_EMPTY items) and valid schema"

echo "[4/9] Baseline scenario execution (baseline_01) - Must produce 0 cases"
curl -fsS -X POST "$SIM/scenarios/baseline_01/start?speed=20&seed=1" >/dev/null
echo "  -> Running baseline scenario for 30s..."
sleep 30

N=$(curl -fsS "${H[@]}" "$API/cases?limit=10" | jq '.items | length')
if [ "$N" -ne 0 ]; then
  echo "FAIL: False positive - case opened on benign baseline ($N cases opened)"
  exit 1
fi
curl -fsS -X POST "$SIM/scenarios/baseline_01/stop" >/dev/null
echo "  -> Baseline cleanly passed with 0 cases opened"

echo "[5/9] Manipulative scenario execution (pump_dump_ring_01)"
curl -fsS -X POST "$SIM/scenarios/pump_dump_ring_01/start?speed=10&seed=42" >/dev/null

echo "[6/9] Await autonomous pipeline case creation (<= 300s)"
CID=""
for i in $(seq 1 60); do
  CID=$(curl -fsS "${H[@]}" "$API/cases?status=PENDING_REVIEW" | jq -r '.items[0].case_id // empty')
  if [ -n "$CID" ]; then
    echo "  -> Case $CID reached PENDING_REVIEW in $((i * 5))s"
    break
  fi
  sleep 5
done

if [ -z "${CID:-}" ]; then
  echo "FAIL: No case reached PENDING_REVIEW within 300s"
  exit 1
fi

echo "[7/9] Graph attribution & trade window account consistency"
GRAPH_RESP=$(curl -fsS "${H[@]}" "$API/cases/$CID/graph")
NODE_COUNT=$(echo "$GRAPH_RESP" | jq '.nodes | length')
if [ "$NODE_COUNT" -lt 5 ]; then
  echo "FAIL: Attribution graph has only $NODE_COUNT nodes (< 5)"
  exit 1
fi
echo "  -> Graph attribution has $NODE_COUNT nodes"

DID=$(curl -fsS "${H[@]}" "$API/cases/$CID/dossiers" | jq -r '.items[0].dossier_id // empty')
if [ -z "$DID" ]; then
  echo "FAIL: No dossier generated for case $CID"
  exit 1
fi

DOSSIER_RESP=$(curl -fsS "${H[@]}" "$API/dossiers/$DID")
ALG=$(echo "$DOSSIER_RESP" | jq -r '.signature.alg')
if [ "$ALG" != "Ed25519" ]; then
  echo "FAIL: Dossier signature alg is '$ALG', expected 'Ed25519'"
  exit 1
fi

EVID_COUNT=$(echo "$DOSSIER_RESP" | jq '.evidence_ids | length')
if [ "$EVID_COUNT" -lt 3 ]; then
  echo "FAIL: Dossier has only $EVID_COUNT evidence items (< 3)"
  exit 1
fi
echo "  -> Dossier $DID verified with Ed25519 signature and $EVID_COUNT evidence citations"

echo "[8/9] Cryptographic evidence & bundle verification"
VERIFY_RES=$(curl -fsS "${H[@]}" "$API/dossiers/$DID/verify" | jq -r '.valid')
if [ "$VERIFY_RES" != "true" ]; then
  echo "FAIL: Dossier verification API returned valid=$VERIFY_RES"
  exit 1
fi
echo "  -> API /dossiers/$DID/verify returned valid=true"

echo "[9/9] Compliance approval, publish gate & tamper detection"
curl -fsS -X POST "${H[@]}" -H 'content-type: application/json' "$API/cases/$CID/review" -d '{"status":"APPROVED","comment":"End-to-end smoke verification"}' >/dev/null

ST=""
for i in $(seq 1 30); do
  ST=$(curl -fsS "${H[@]}" "$API/cases/$CID" | jq -r .status)
  if [ "$ST" = "PUBLISHED" ]; then
    echo "  -> Case $CID transition to PUBLISHED verified"
    break
  fi
  sleep 3
done

if [ "$ST" != "PUBLISHED" ]; then
  echo "FAIL: Case did not reach PUBLISHED status (current: $ST)"
  exit 1
fi

LATEST=$(curl -fsS "${H[@]}" "$API/cases/$CID/dossiers" | jq -r '.items[0].dossier_id')
curl -fsS "${H[@]}" "$API/dossiers/$LATEST/bundle" -o /tmp/vigil_bundle.zip

if ! uv run vigil-verify /tmp/vigil_bundle.zip --pubkey keys/dev_ed25519.pub >/dev/null 2>&1; then
  echo "FAIL: Offline vigil-verify CLI failed on signed bundle"
  exit 1
fi
echo "  -> Offline CLI vigil-verify verified valid bundle"

# Tamper test: flip byte in zip archive
cp /tmp/vigil_bundle.zip /tmp/tampered.zip
printf '\x00' | dd of=/tmp/tampered.zip bs=1 seek=200 count=1 conv=notrunc 2>/dev/null
if uv run vigil-verify /tmp/tampered.zip --pubkey keys/dev_ed25519.pub >/dev/null 2>&1; then
  echo "FAIL: Byte tampering was NOT detected by verifier!"
  exit 1
fi
echo "  -> Byte tampering detected and rejected with non-zero exit code"

# Clean up
rm -f /tmp/vigil_bundle.zip /tmp/tampered.zip
curl -fsS -X POST "$SIM/scenarios/pump_dump_ring_01/stop" >/dev/null 2>&1 || true

echo "================================================================================"
echo "SMOKE TEST PASSED: ALL ACCEPTANCE CHECKS OK"
echo "================================================================================"
