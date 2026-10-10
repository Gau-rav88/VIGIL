# Project VIGIL: Production Operator Runbook

**System:** Project VIGIL Autonomous Market Surveillance & Forensic Platform  
**Version:** v1.0.0  
**Scope:** Operations, Disaster Recovery, Key Rotation & Incident Response  
**Classification:** Internal Forensic Workbench  

---

## 1. System Lifecycle Operations

### 1.1 Stack Initialization & Boot
To bootstrap the complete 14-service multi-agent cluster:
```bash
# Generate development keys and boot Docker compose stack
make up

# Wait for all health checks to report healthy
./scripts/wait_for_stack.sh
```

Stack components verified:
- **Core Datastores:** TimescaleDB (pg16, port 5434), Neo4j Community (port 7474/7687), Redis 7 (port 6379), Redpanda (port 19092), MinIO (port 9000/9001).
- **Processing Plane:** `market_ingest`, `social_ingest`, `stream_sink`, `quant_telemetry`, `social_intel`, `alignment_engine`, `attribution`, `evidence_engine`, `orchestrator`.
- **Serving Plane:** FastAPI Serving Plane (port 8001), Next.js Workbench UI (port 3000), Simulator (port 8090).
- **Observability Plane:** Prometheus (port 9090), Grafana (port 3001), OpenTelemetry Collector (port 4317).

### 1.2 Graceful Shutdown & Teardown
```bash
# Graceful stop preserving volumes and state
make down

# Complete volume wipe and fresh initialization (caution: destroys all forensic state)
make nuke
```

### 1.3 Service Health Probes
All services expose HTTP health probes on port 8000 (or respective service ports):
- Ingress Liveness: `curl -fsS http://localhost:8001/healthz`
- Ingress Readiness: `curl -fsS http://localhost:8001/readyz`
- Prometheus Metrics: `curl -fsS http://localhost:8001/metrics`
- Simulator Health: `curl -fsS http://localhost:8090/healthz`

---

## 2. Cryptographic Secret & Key Rotation Runbook

### 2.1 Ed25519 Signing Key Rotation
Project VIGIL digitally signs every RFC 8785 forensic dossier using Ed25519 asymmetric cryptography.

**Rotation Procedure:**
1. Generate new Ed25519 keypair with an incremented Key ID (e.g., `prod-2026-02`):
   ```bash
   openssl genpkey -algorithm Ed25519 -out keys/prod_2026_02.pem
   openssl pkey -in keys/prod_2026_02.pem -pubout -out keys/prod_2026_02.pub
   ```
2. Distribute public key `keys/prod_2026_02.pub` to the offline verifier directory and registry.
3. Update environment configuration:
   ```bash
   SIGNER_KEY_ID="prod-2026-02"
   SIGNER_KEY_PATH="/secrets/prod_2026_02.pem"
   ```
4. Restart `evidence_engine` and `api` services:
   ```bash
   docker compose restart evidence_engine api
   ```
5. **Backwards Compatibility:** Old public keys must be retained in the public key registry to allow `vigil-verify` to validate historical cases signed under previous Key IDs.

### 2.2 JWT Authentication Secret Rotation
1. Update `JWT_SECRET` in `.env` with at least 256 bits of high entropy:
   ```bash
   openssl rand -hex 32
   ```
2. Restart `api` service. Active user sessions will expire and require re-authentication.

### 2.3 Pseudonymization HMAC Pepper Rotation
> [!WARNING]
> Rotating `PSEUDONYM_PEPPER` changes the deterministic pseudonymization hash output. Historical data will remain linked under the old pseudonym unless a batch migration script re-hashes historical identifiers.

---

## 3. Disaster Recovery (DR) & Backup Procedures

### 3.1 TimescaleDB Backup & Restore
- **Target Hypertable:** `vigil.trades`, `vigil.mrs_1m`, `vigil.cases`, `vigil.evidence_ledger`
- **Backup (Logical Dump):**
  ```bash
  docker exec vigil-timescale-1 pg_dump -U vigil -d vigil -F c -b -v -f /tmp/vigil_backup.dump
  docker cp vigil-timescale-1:/tmp/vigil_backup.dump ./backups/
  ```
- **Restore:**
  ```bash
  docker cp ./backups/vigil_backup.dump vigil-timescale-1:/tmp/
  docker exec vigil-timescale-1 pg_restore -U vigil -d vigil --clean --if-exists /tmp/vigil_backup.dump
  ```
- **Target RTO:** < 30 seconds  
- **Target RPO:** 0 seconds (when combined with Redpanda WAL replay)

### 3.2 Neo4j Graph Database Backup & Restore
- **Backup:**
  ```bash
  docker exec vigil-neo4j-1 neo4j-admin database dump neo4j --to-path=/tmp/
  docker cp vigil-neo4j-1:/tmp/neo4j.dump ./backups/
  ```
- **Restore:**
  ```bash
  docker compose stop neo4j
  docker cp ./backups/neo4j.dump vigil-neo4j-1:/tmp/
  docker exec vigil-neo4j-1 neo4j-admin database load neo4j --from-path=/tmp/ --overwrite-destination=true
  docker compose start neo4j
  ```

### 3.3 MinIO S3 Object Store Backup
- **Forensic S3 Bucket:** `vigil-evidence`
- **Sync / Replication:**
  ```bash
  aws --endpoint-url http://localhost:9000 s3 sync s3://vigil-evidence/ ./backups/minio/
  ```

---

## 4. Dead Letter Queue (DLQ) Recovery & Replay

When ingestion pipelines encounter malformed payloads or unpermitted visibility flags, messages are routed to:
- `dlq.market`: Unparseable market feed payloads or schema validation failures.
- `dlq.social`: Rejected non-public posts (`VISIBILITY_NOT_PERMITTED`) or corrupt JSON.

### 4.1 DLQ Inspection
```bash
# Tail DLQ topic using Redpanda console or rpk
docker exec vigil-redpanda-1 rpk topic consume dlq.market -n 10
```

### 4.2 DLQ Replay Runbook
1. Inspect `error` and `original_b64` attributes in DLQ message.
2. If cause was transient schema drift, deploy updated schema adapter.
3. Re-ingest decoded payload using replay adapter:
   ```bash
   uv run python -m vigil_common.replay --file /tmp/dlq_payload.jsonl --speed 1.0
   ```

---

## 5. Troubleshooting & Triage Matrix

| Symptom | Probable Cause | Diagnostic Command | Remediation |
|---|---|---|---|
| **High Consumer Lag Alert** | Ingestion spike exceeding single-threaded consumer | `docker exec vigil-redpanda-1 rpk group describe vigil-stream-sink` | Scale consumer partitions or verify Timescale write latency |
| **SIGNER_DOWN Alert** | Key file permissions or disk read error | `docker compose logs evidence_engine --tail=50` | Verify `keys/dev_ed25519.pem` exists and readable |
| **Ledger Verify Failure** | Database row modification or tamper attempt | `curl -s -H "Authorization: Bearer $T" http://localhost:8001/api/v1/ledger/verify` | Trigger security alert; examine postgres audit logs for unauthorized SQL |
| **Neo4j Memory Exhaustion** | Heavy Louvain / WCC execution on unindexed nodes | `docker stats vigil-neo4j-1` | Restart Neo4j; ensure batch size limits (`max_nodes <= 500`) |
