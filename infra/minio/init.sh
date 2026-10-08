#!/usr/bin/env sh
set -e

echo "Initializing MinIO buckets for VIGIL..."

mc alias set local http://minio:9000 vigil vigilvigil123

for bucket in vigil-raw vigil-evidence vigil-dossiers vigil-anchors; do
  mc mb local/$bucket --ignore-existing
done

echo "MinIO buckets initialized successfully."
