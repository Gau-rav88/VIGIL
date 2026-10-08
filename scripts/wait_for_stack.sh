#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for core infrastructure to become healthy..."

# 1. TimescaleDB
echo "Waiting for TimescaleDB..."
for i in $(seq 1 30); do
  if docker compose exec -T timescale pg_isready -U vigil -d vigil >/dev/null 2>&1; then
    echo "TimescaleDB is ready."
    break
  fi
  sleep 2
done

# 2. Redis
echo "Waiting for Redis..."
for i in $(seq 1 20); do
  if docker compose exec -T redis redis-cli ping >/dev/null 2>&1; then
    echo "Redis is ready."
    break
  fi
  sleep 2
done

# 3. Neo4j
echo "Waiting for Neo4j..."
for i in $(seq 1 30); do
  if docker compose exec -T neo4j cypher-shell -u neo4j -p vigilneo4j "RETURN 1" >/dev/null 2>&1; then
    echo "Neo4j is ready."
    break
  fi
  sleep 3
done

# 4. Redpanda
echo "Waiting for Redpanda..."
for i in $(seq 1 30); do
  if docker compose exec -T redpanda rpk cluster health | grep -q "Healthy:.*true" 2>/dev/null; then
    echo "Redpanda is ready."
    break
  fi
  sleep 2
done

# 5. API
echo "Waiting for VIGIL API..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then
    echo "API is ready."
    break
  fi
  sleep 2
done

echo "All core services are online and ready."
