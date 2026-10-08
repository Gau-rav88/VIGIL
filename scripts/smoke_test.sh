#!/usr/bin/env bash
set -euo pipefail

API=${API:-http://localhost:8000/api/v1}
SIM=${SIM:-http://localhost:8090}

echo "[1/8] health check"
for s in healthz readyz; do
  curl -fsS "http://localhost:8000/$s" >/dev/null
done

echo "[2/8] dev token issuance"
TOKEN=$(curl -fsS -X POST "$API/auth/dev-token" -H 'content-type: application/json' -d '{"sub":"smoke-c","role":"compliance_officer"}' | jq -r .token)
H=(-H "authorization: Bearer $TOKEN")

echo "[3/8] baseline 60s scenario"
curl -fsS -X POST "$SIM/scenarios/baseline_01/start?speed=20&seed=1" >/dev/null
sleep 60
N=$(curl -fsS "${H[@]}" "$API/cases?limit=1" | jq '.items|length')
[ "$N" -eq 0 ] || { echo "FAIL: case opened on baseline"; exit 1; }
curl -fsS -X POST "$SIM/scenarios/baseline_01/stop" >/dev/null

echo "[4/8] pump scenario (pump_dump_ring_01)"
curl -fsS -X POST "$SIM/scenarios/pump_dump_ring_01/start?speed=10&seed=42" >/dev/null

echo "[5/8] wait for case (<=300s)"
CID=""
for i in $(seq 1 60); do
  CID=$(curl -fsS "${H[@]}" "$API/cases?symbol=ZENITHSME&status=PENDING_REVIEW" | jq -r '.items[0].case_id // empty')
  [ -n "$CID" ] && break
  sleep 5
done
[ -n "${CID:-}" ] || { echo "FAIL: no case reached PENDING_REVIEW"; exit 1; }

echo "[6/8] graph + ring check"
curl -fsS "${H[@]}" "$API/cases/$CID/graph" | jq -e '.nodes|length>=15' >/dev/null
DID=$(curl -fsS "${H[@]}" "$API/cases/$CID/dossiers" | jq -r '.items[0].dossier_id')
curl -fsS "${H[@]}" "$API/dossiers/$DID" | jq -e '.attribution.rings[0].ring_score>=0.8 and .signature.alg=="Ed25519"' >/dev/null

echo "[7/8] verification"
curl -fsS "${H[@]}" "$API/dossiers/$DID/verify" | jq -e '.valid==true' >/dev/null

echo "[8/8] approve + publish"
curl -fsS -X POST "${H[@]}" -H 'content-type: application/json' "$API/cases/$CID/review" -d '{"status":"APPROVED","comment":"smoke"}' >/dev/null
ST=""
for i in $(seq 1 24); do
  ST=$(curl -fsS "${H[@]}" "$API/cases/$CID" | jq -r .status)
  [ "$ST" = "PUBLISHED" ] && break
  sleep 5
done
[ "$ST" = "PUBLISHED" ] || { echo "FAIL: not published"; exit 1; }

LATEST=$(curl -fsS "${H[@]}" "$API/cases/$CID/dossiers" | jq -r '.items[0].dossier_id')
curl -fsS "${H[@]}" "$API/dossiers/$LATEST/bundle" -o /tmp/vigil_bundle.zip
uv run vigil-verify /tmp/vigil_bundle.zip --pubkey keys/dev_ed25519.pub

# Tamper test
cp /tmp/vigil_bundle.zip /tmp/tampered.zip
printf '\x00' | dd of=/tmp/tampered.zip bs=1 seek=200 count=1 conv=notrunc 2>/dev/null
! uv run vigil-verify /tmp/tampered.zip --pubkey keys/dev_ed25519.pub || { echo "FAIL: tamper not detected"; exit 1; }

echo "SMOKE TEST PASSED: ALL ACCEPTANCE CHECKS OK"
