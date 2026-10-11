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
hype.scores.norm:8
anomaly.market:8
anomaly.social:8
anomaly.fused:8
graph.updates:8
case.trigger:4
case.events:4
health.events:1
dlq.market:2
dlq.social:2
dlq.sink:2
"

BROKERS="${KAFKA_BOOTSTRAP:-redpanda:9092}"

for item in $TOPICS; do
  [ -z "$item" ] && continue
  TOPIC=$(echo "$item" | cut -d: -f1)
  PARTITIONS=$(echo "$item" | cut -d: -f2)
  echo "Ensuring topic: ${TOPIC} (partitions: ${PARTITIONS})"
  out=$(rpk topic create "${TOPIC}" -p "${PARTITIONS}" --brokers "${BROKERS}" 2>&1) || {
    echo "$out" | grep -qi -E "already.*exists" || {
      echo "ERROR: Failed creating topic ${TOPIC}: $out" >&2
      exit 1
    }
  }
done

echo "Verifying created topics with rpk topic list..."
topic_list=$(rpk topic list --brokers "${BROKERS}")

for item in $TOPICS; do
  [ -z "$item" ] && continue
  TOPIC=$(echo "$item" | cut -d: -f1)
  if ! echo "$topic_list" | grep -q "${TOPIC}"; then
    echo "ERROR: Topic ${TOPIC} was not found in rpk topic list!" >&2
    exit 1
  fi
done

echo "Redpanda topic initialization complete and verified."
