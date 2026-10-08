#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for Neo4j bolt..."
until cypher-shell -u neo4j -p vigilneo4j "RETURN 1" >/dev/null 2>&1; do
  sleep 2
done

echo "Applying Neo4j constraints..."
if [ -f /migrations/neo4j/001_constraints.cypher ]; then
  cypher-shell -u neo4j -p vigilneo4j -f /migrations/neo4j/001_constraints.cypher
fi

if [ -f /migrations/neo4j/002_indexes.cypher ]; then
  cypher-shell -u neo4j -p vigilneo4j -f /migrations/neo4j/002_indexes.cypher
fi

echo "Neo4j schema initialized."
