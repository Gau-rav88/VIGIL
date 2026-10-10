# Project VIGIL: Production Readiness & Architecture Notes

**Document Version:** 1.0.0  
**Scope:** Post-MVP Production Scaling, Cloud Architecture, Managed Infrastructure & Enterprise Security  
**Status:** REFERENCE SPECIFICATION  

---

## 1. Enterprise Target Architecture

In a production regulatory or exchange environment, Project VIGIL transitions from single-node Docker Compose to a multi-AZ Kubernetes deployment across private VPC subnets.

```
+-------------------------------------------------------------------------+
|                              INGRESS / WAF                              |
|         AWS ALB / Cloudflare WAF (TLS 1.3, Rate Limits, CSP/HSTS)        |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------+------------------------------------+
|                         SERVING PLANE EKS                               |
|   FastAPI Pods (HPA) | Next.js Workbench Pods | OIDC / Okta Auth Gate   |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------+------------------------------------+
|                        EVENT BUS & STREAMING                            |
|     Managed Redpanda Cluster / Amazon MSK (Multi-AZ, 3 Brokers)         |
+------------------------------------+------------------------------------+
        |                            |                            |
+-------v---------+        +---------v--------+        +----------v-------+
| INGESTION PODS  |        | DETECTION PODS   |        | GRAPH / AGENTS   |
| L2/L3/Trades    |        | Quant Telemetry  |        | Neo4j Cluster    |
| Social Scrapers |        | Social Intel     |        | LangGraph ORC    |
+-----------------+        +------------------+        +------------------+
        |                            |                            |
+-------v----------------------------v----------------------------v-------+
|                         ENTERPRISE DATASTORES                           |
|  Timescale Cloud (Hypertables) | Neo4j Enterprise | AWS KMS / Vault HSM |
+-------------------------------------------------------------------------+
```

---

## 2. Key Management Service (KMS) & Cloud HSM

The development environment employs `FileEd25519Signer` backed by local PEM files in `keys/`. For production operations, private keys must NEVER reside on container filesystems.

### 2.1 AWS KMS / Cloud HSM Provider Architecture
- **Key Spec:** Asymmetric signing key using `ECC_ED25519` or `RSA_4096`.
- **Interface:** Implement `KmsEd25519Signer` implementing `vigil_common.signing.Signer`:
  ```python
  import boto3
  from vigil_common.signing import Signer

  class AwsKmsSigner(Signer):
      def __init__(self, key_id: str):
          self.client = boto3.client("kms")
          self.key_id = key_id

      async def sign(self, canonical_payload: bytes) -> bytes:
          response = self.client.sign(
              KeyId=self.key_id,
              Message=canonical_payload,
              MessageType="RAW",
              SigningAlgorithm="ED25519",
          )
          return response["Signature"]
  ```
- **FIPS 140-3 Compliance:** Keys reside in HSM hardware modules rated FIPS 140-3 Level 3 with strict IAM access policies and CloudTrail audit logging.

---

## 3. Managed Streaming Infrastructure (Kafka / Redpanda)

For production loads exceeding 50,000 market ev/s and multi-terabyte order book histories:
1. **Cluster Topology:** 3-node or 5-node Redpanda Enterprise or AWS MSK cluster distributed across 3 Availability Zones.
2. **Replication Factor:** `replication_factor=3` with `min_insync_replicas=2`.
3. **Partitioning Scheme:**
   - `market.trades`: 16 partitions keyed by `symbol` ensuring strict per-ticker sequence preservation.
   - `social.raw`: 8 partitions keyed by `channel_id`.
   - `anomaly.fused`: 4 partitions keyed by `case_id` or `symbol`.
4. **Retention Policies:** 7 days rolling retention on raw tick topics; compacted log enabled for watchlist state.

---

## 4. Neo4j Enterprise Clustering & Graph Data Science (GDS)

1. **Topology:** Autonomous Clustering with 3 Core servers (Raft consensus) and 2 Read Replicas dedicated to investigator web UI Cytoscape queries.
2. **Memory Allocation:**
   - Initial heap: 32 GB (`server.memory.heap.initial_size=32g`).
   - Pagecache: 64 GB (`server.memory.pagecache.size=64g`).
3. **Graph Data Science License:**
   - In production, license Neo4j GDS Enterprise for GPU-accelerated Louvain community detection and FastRP node embeddings across 100M+ trading accounts.

---

## 5. Multi-Region Deployment & Disaster Recovery

- **Primary Region:** `ap-south-1` (Mumbai, proximity to NSE/BSE colocation).
- **Secondary DR Region:** `ap-southeast-1` (Singapore).
- **RTO / RPO Target:** RTO < 5 minutes, RPO < 1 second.
- **Cross-Region Replication:**
  - Timescale: Managed streaming replication to read-replica with automated failover.
  - S3 Object Lock: Cross-region replication (CRR) to immutable compliance bucket in secondary region with Legal Hold enabled.

---

## 6. Enterprise Identity & OIDC Integration

Replace development token generation (`/api/v1/auth/dev-token`) with enterprise OAuth 2.0 / OpenID Connect (OIDC):
1. **Identity Providers:** Okta, Ping Identity, Azure Entra ID, or Keycloak.
2. **Token Flow:** Authorization Code Flow with PKCE.
3. **Role Mapping:**
   - `groups.includes("vigil-investigators")` -> role: `investigator`
   - `groups.includes("vigil-compliance-officers")` -> role: `compliance_officer`
   - `groups.includes("vigil-admins")` -> role: `admin`
   - `groups.includes("vigil-auditors")` -> role: `auditor_readonly`
4. **MFA Enforcement:** Hardware WebAuthn/FIDO2 security keys mandatory for all privileged operations (KYC unmasking, case publishing).
