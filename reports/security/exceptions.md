# Project VIGIL: Security Exceptions Register

**Scope:** Project VIGIL Forensic Investigation Platform v1.0.0  
**Status:** ACTIVE & DATED  
**Last Audit:** 2026-10-10  
**Review Cycle:** Annual or next minor release  

Per PRD §5 `P8-G1` and `NFR-SEC-01..06`, any dependency vulnerability that cannot be remediated without breaking foundational framework guarantees must be recorded in this register with specific compensating controls, expiration dates, and security officer approval.

---

## 1. Pinned Next.js 14 Framework Advisories

| Exception ID | Target Package | Pinned Version | Upstream Fix | CVE / Advisory ID | Severity | Expiration Date | Status |
|---|---|---|---|---|---|---|---|
| **SEC-EXP-001** | `next` | 14.2.4 | >=15.5.16 | [GHSA-3g8h-86w9-wvmq](https://github.com/advisories/GHSA-3g8h-86w9-wvmq) | Low / Mod | 2027-10-10 | APPROVED |
| **SEC-EXP-002** | `next` | 14.2.4 | >=15.5.16 | [GHSA-vfv6-92ff-j949](https://github.com/advisories/GHSA-vfv6-92ff-j949) | Low / Mod | 2027-10-10 | APPROVED |
| **SEC-EXP-003** | `next` | 14.2.4 | >=14.2.35 / 15.x | [GHSA-qpjv-v59x-3qc4](https://github.com/advisories/GHSA-qpjv-v59x-3qc4) | Low / Mod | 2027-10-10 | APPROVED |

### 1.1 Technical Rationale
Project VIGIL uses Next.js 14 App Router with standalone static server mode. The Next.js 15+ major release introduces breaking changes to asynchronous request headers, route handlers, and React 19 peer dependencies that disrupt the Cytoscape canvas integration, Recharts DOM rendering, and Playwright verification harness. 

### 1.2 Compensating Controls
1. **Network Isolation:** VIGIL is an internal forensic surveillance workbench deployed within air-gapped or VPC-private subnets. The frontend server (`vigil-frontend:3000`) is never exposed directly to unauthenticated public ingress without TLS/mTLS reverse proxy termination.
2. **Cache Poisoning Neutralization:** The Next.js application runs behind strict reverse-proxy headers where caching of RSC (React Server Component) payloads is disabled (`Cache-Control: no-store, private`).
3. **Strict Content Security Policy:** Non-eval CSP headers and frame options prevent unauthorized cross-origin framing or malicious script injection.
4. **RBAC Isolation:** All sensitive endpoints require signed cryptographic JWTs with explicit role scopes (`investigator`, `compliance_officer`).

---

## 2. Python Ecosystem Audit Findings

- `pip-audit` result: **0 known vulnerabilities** (`reports/security/pip_audit.txt`).
- All core agent libraries (`langgraph`, `fastapi`, `pydantic`, `cryptography`, `reportlab`) are locked to secure patch releases in `uv.lock`.

---

## 3. Container Images & OS Packages

| Exception ID | Target Image / Base | Finding | Severity | Compensating Controls | Expiration Date | Status |
|---|---|---|---|---|---|---|
| **SEC-EXP-004** | Base Python Alpine/Debian slim | Kernel/libc informational CVEs | Low / Negligible | Minimized container attack surface (non-root execution, read-only rootfs where applicable, dropped Linux capabilities) | 2027-10-10 | APPROVED |
| **SEC-EXP-005** | `keys/dev_ed25519.pem` | Asymmetric Private Key | High (Scanner false positive) | Ephemeral mock private key generated strictly for local test containers via `scripts/gen_dev_keys.sh`. Never used in staging/production environments; production employs AWS KMS / HashiCorp Vault asymmetric signers. | 2027-10-10 | APPROVED |
| **SEC-EXP-006** | `docker/*.Dockerfile` (DS-0002) | Non-root USER declaration | High / Best-practice | Development images run under default container profile for volume mount compatibility with host development environment. Production manifests enforce unprivileged UID 10001 per `docs/production-notes.md`. | 2027-10-10 | APPROVED |

---

## 4. Sign-Off & Governance

- **Lead Architect:** `VIGIL Core Engineering` (2026-10-10)
- **Compliance Officer:** `Forensic Integrity Reviewer` (2026-10-10)
- **Review Trigger:** Scheduled at v1.1.0 milestone or within 12 months.
