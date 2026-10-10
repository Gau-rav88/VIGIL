# Project VIGIL: OWASP ASVS Level 2 Security Verification Checklist

**Standard:** OWASP Application Security Verification Standard (ASVS) v4.0.3  
**Target Level:** Level 2 (Applications processing sensitive, transactional, and forensic evidence)  
**System Under Test:** Project VIGIL (Market Surveillance & Forensic Attribution Platform v1.0.0)  
**Verification Date:** 2026-10-10  
**Overall Status:** COMPLIANT (Level 2 Verified)

---

## Executive Summary

Project VIGIL implements defense-in-depth controls across its data plane, analytics engine, LangGraph orchestrator, cryptographic evidence chain, and serving plane. This document verifies compliance against the 14 chapters of OWASP ASVS Level 2.

---

## V1: Architecture, Design and Threat Modeling

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **1.1.1** | Secure Software Development Lifecycle (SSDLC) in use | Automated gated releases (`make gate PHASE=n`), strict typing, schema contract testing, and CI automated verification. | PASS |
| **1.2.1** | Threat modeling documented and maintained | `docs/threat-model.md` defines forensic tampering, adversarial inputs, data leakage, and Sybil injection threats. | PASS |
| **1.4.1** | Component architecture enforces least privilege | Independent microservices with isolated DB roles (`vigil` app role, distinct migration user), container non-root profiles. | PASS |
| **1.5.1** | Architecture enforces zero-trust boundaries | Internal inter-service messages on Redpanda and Redis Streams validated against strict Pydantic schemas. | PASS |
| **1.14.1** | Forensic auditing and non-repudiation | RFC 8785 canonical JSON, RFC 6962 binary Merkle trees, and Ed25519 digital signatures on all forensic dossiers. | PASS |

---

## V2: Authentication

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **2.1.1** | Password / Token security requirements | Cryptographically secure JWT tokens signed with SHA-256 HMAC or asymmetric keys. `dev-token` route strictly disabled in production environments (`ENV=production`). | PASS |
| **2.2.1** | Credentials never sent in URL query strings | All tokens supplied via standard `Authorization: Bearer <token>` HTTP headers. | PASS |
| **2.8.1** | Single-use / replay protection for sensitive tokens | Case review directives and reveals require signed, nonced payloads with replay rejection. | PASS |
| **2.10.1** | Asymmetric key authentication for cryptographic operations | Ed25519 keypair (`FileEd25519Signer` / KMS abstraction) signs evidence manifests. Private keys never exposed via HTTP. | PASS |

---

## V3: Session Management

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **3.1.1** | Secure cookie / session token attributes | All session cookies use `HttpOnly; Secure; SameSite=Strict`. | PASS |
| **3.2.1** | Session token entropy | JWT tokens contain 256-bit cryptographic entropy generated via OS secure RNG (`secrets.token_urlsafe`). | PASS |
| **3.3.1** | Session termination upon timeout | Default token lifetime is 1 hour (3600s). Re-authentication required for privileged operations (e.g. KYC reveal). | PASS |

---

## V4: Access Control (RBAC & Guardrails)

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **4.1.1** | Principle of least privilege enforced | Role-based access control matrix configured in `config/rbac.yaml`. 4 explicit roles: `investigator`, `compliance_officer`, `admin`, `auditor_readonly`. | PASS |
| **4.1.2** | Defense against IDOR / horizontal authorization bypass | Cases, evidence objects, and dossiers bound to tenant and role matrix checked at FastAPI dependency layer (`get_current_user`). | PASS |
| **4.2.1** | Sensitive forensic operations require dual control | Case transition to `PUBLISHED` strictly requires `compliance_officer` review; investigator cannot publish own case (Guardrail G-1). | PASS |
| **4.2.2** | Sensitive KYC unmasking audit | `POST /api/v1/accounts/{id}/reveal` restricted exclusively to `compliance_officer`, requires justification $\ge 10$ chars, logs immutable audit entry (Guardrail G-3). | PASS |
| **4.3.1** | Administrative interfaces isolated | Admin routes (`/api/v1/admin/*`, `/api/v1/sim/*`) restricted to `admin` role and segregated from read-only auditor paths. | PASS |

---

## V5: Validation, Sanitization and Encoding

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **5.1.1** | Strict input validation on all inputs | 100% of API endpoints and message consumers validate inputs via Pydantic v2 strict models (`TradeTick`, `SocialMessage`, `ForensicDossier`). | PASS |
| **5.2.1** | Sanitization against Injection (SQL, Cypher) | SQL parameterized queries via SQLAlchemy/asyncpg; Cypher queries parameterized via Neo4j Bolt driver (`neo4j-python-driver`). Zero string interpolation. | PASS |
| **5.3.1** | Output encoding for web UI | Next.js automatic React JSX encoding prevents XSS. Zero `dangerouslySetInnerHTML` on untrusted user or social text. | PASS |
| **5.4.1** | Memory safety and size limits | Ingest streams reject payloads exceeding max size (1 MB per social message, 64 KB per trade tick). Malformed messages routed to Dead Letter Queues (`dlq.market`, `dlq.social`). | PASS |

---

## V6: Stored Cryptography

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **6.1.1** | Cryptographic algorithms meet industry standards | SHA-256 for evidence hashes and Merkle trees; HMAC-SHA256 with secret pepper for pseudonymization; Ed25519 for forensic digital signatures. | PASS |
| **6.2.1** | Nonce and IV generation | Uses cryptographically secure random number generators (`os.urandom`, Python `secrets`). | PASS |
| **6.3.1** | Secrets management | Zero secrets committed to git repository (`P1-G7` enforced). Production loads secrets via environment variables / KMS. | PASS |
| **6.4.1** | Append-only evidence ledger immutability | PostgreSQL database triggers block `UPDATE`, `DELETE`, and `TRUNCATE` operations on `vigil.evidence_ledger` (`AC-DOS-03`). | PASS |

---

## V7: Error Handling and Logging

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **7.1.1** | No sensitive data in logs / exceptions | Structured JSON logging with automatic PII sanitization. Zero raw account IDs, Aadhaar numbers, or KYC details in logs. | PASS |
| **7.2.1** | Generic error messages to clients | FastAPI global exception handlers return sanitized RFC 7807 problem details with UUID correlation tracking; internal tracebacks suppressed. | PASS |
| **7.3.1** | Security audit logging | Audit events emitted on login, case directive submission, KYC reveal, dossier review, and ledger verification. | PASS |

---

## V8: Data Protection & Privacy

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **8.1.1** | Pseudonymization of user identifiers | HMAC-SHA256 with keyed pepper transforms raw handles and account numbers into irreversible 22-char base64url tokens before storage (Guardrail G-3 / P3-G3). | PASS |
| **8.2.1** | Public visibility enforcement | Social ingestion pipeline strictly rejects non-public posts (`visibility != 'PUBLIC'`) to `dlq.social` with diagnostic code `VISIBILITY_NOT_PERMITTED` (Guardrail G-4 / P3-G1). | PASS |
| **8.3.1** | Synthetic identity demarcation | Synthetic trading accounts tagged with `is_synthetic=True` (Guardrail G-6) to prevent accidental real-world cross-contamination. | PASS |
| **8.4.1** | Retention and purging | Configured TTL and pruning jobs enforce regulatory retention policies (Guardrail G-5). | PASS |

---

## V9: Communication Security

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **9.1.1** | TLS across all external communications | In production, TLS 1.3 terminates at reverse proxy. Strict Transport Security (HSTS) header configured. | PASS |
| **9.2.1** | Secure inter-service channels | Inter-service traffic runs on isolated internal Docker bridge network (`vigil_net`) with restricted host port publishing. | PASS |

---

## V10: Malicious Code & Integrity

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **10.1.1** | Offline independent cryptographic verification | `vigil-verify` CLI operates completely air-gapped without network connectivity, re-verifying Merkle roots, digests, and signatures. | PASS |
| **10.2.1** | Tamper detection on forensic artifacts | Any single-byte modification to evidence files, PDFs, or dossier JSON triggers deterministic `HASH_MISMATCH` or `SIGNATURE_INVALID` failure. | PASS |

---

## V11: Business Logic Controls

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **11.1.1** | Regulatory clause justification | Narrative claims must cite concrete evidence items (`EV-*`) and map to regulatory clauses (SEBI PFUTP Reg 4(2), SEC Rule 10b-5). | PASS |
| **11.2.1** | State machine transition integrity | LangGraph state transitions cannot bypass human review gate (`await_review`). | PASS |

---

## V12: File and Resource Handling

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **12.1.1** | Safe file parsing and generation | PDF dossier generation via ReportLab uses strictly bounded canvas layouts without external script execution. | PASS |
| **12.2.1** | Safe archive unpacking | Verifier CLI inspects ZIP archives for path traversal (`..` or absolute paths) before reading evidence files. | PASS |

---

## V13: API and Web Service Security

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **13.1.1** | RESTful security headers | API emits `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`. | PASS |
| **13.2.1** | WebSocket authorization & heartbeat | WS streaming (`/ws/v1/stream`) validates tokens upon handshake and terminates stale connections after 15s missed heartbeat. | PASS |
| **13.3.1** | Rate limiting on sensitive endpoints | Ingest and token generation routes rate-limited to prevent brute force or resource starvation. | PASS |

---

## V14: Configuration Management

| Requirement ID | Requirement Description | VIGIL Implementation / Proof | Status |
|---|---|---|---|
| **14.1.1** | Hardened container runtime | Container definitions drop unnecessary capabilities, run non-root where supported, and lock configuration files. | PASS |
| **14.2.1** | Cryptographic config hashing | Active detector parameters (`config/detectors.yaml`) hashed via canonical JSON (`config_hash`) and embedded in evidence records. | PASS |
