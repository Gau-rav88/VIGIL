#!/usr/bin/env bash
set -euo pipefail

TARGET_SVC="${1:-}"

if [[ -n "$TARGET_SVC" ]]; then
  echo "Targeted chaos test for service: $TARGET_SVC"
  echo "Stopping $TARGET_SVC..."
  docker compose stop "$TARGET_SVC" || true
  echo "$TARGET_SVC stopped. Simulating outage..."
  sleep 10
  echo "Restarting $TARGET_SVC..."
  docker compose start "$TARGET_SVC" || true
  sleep 5
  ./scripts/wait_for_stack.sh
  echo "Targeted chaos test for $TARGET_SVC passed."
  exit 0
fi

echo "Starting VIGIL chaos resilience test across all core services..."
SERVICES=("redpanda" "timescale" "neo4j" "redis")

for svc in "${SERVICES[@]}"; do
  echo "Pausing $svc for 10 seconds..."
  docker compose pause "$svc" || true
  sleep 10
  echo "Resuming $svc..."
  docker compose unpause "$svc" || true
  sleep 5
done

echo "Chaos test completed. Verifying stack health..."
./scripts/wait_for_stack.sh
echo "Chaos test passed."
