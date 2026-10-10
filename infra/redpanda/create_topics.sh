#!/bin/sh
set -e

echo "Creating Redpanda / Kafka topics for VIGIL..."

TOPICS="
market.trades.raw:16
market.l2.raw:16
market.l3.raw:16
market.trades.norm:16
market.l2.norm:16
market.l3.norm:16
social.messages.raw:8
social.signals.norm:8
anomaly.market:8
anomaly.social:8
anomaly.fused:8
graph.updates:8
case.trigger:4
case.events:4
health.events:1
dlq.market:2
dlq.social:2
"

for item in $TOPICS; do
  [ -z "$item" ] && continue
  TOPIC=$(echo "$item" | cut -d: -f1)
  PARTITIONS=$(echo "$item" | cut -d: -f2)
  echo "Ensuring topic: ${TOPIC} (partitions: ${PARTITIONS})"
  rpk topic create "${TOPIC}" -p "${PARTITIONS}" --brokers "redpanda:9092" || true
done

echo "Redpanda topic initialization complete."
