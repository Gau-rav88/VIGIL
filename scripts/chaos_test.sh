#!/usr/bin/env bash
set -euo pipefail

echo "Starting VIGIL chaos resilience test..."
SERVICES=("redpanda" "timescale" "neo4j" "redis")

for svc in "${SERVICES[@]}"; do
  echo "Pausing $svc for 15 seconds..."
  docker compose pause "$svc" || true
  sleep 15
  echo "Resuming $svc..."
  docker compose unpause "$svc" || true
  sleep 5
done

echo "Chaos test completed. Verifying stack health..."
./scripts/wait_for_stack.sh
echo "Chaos test passed."
