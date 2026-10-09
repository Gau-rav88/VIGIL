# PRD v2 — Project VIGIL
### Autonomous Multi-Agent Forensic Intelligence Platform for Capital-Market Manipulation
### Delivered in 8 gated phases, built by an AI coding agent (Antigravity) one phase at a time

| Field | Value |
|---|---|
| Document version | 2.0.0 (supersedes PRD v1.0.0, which moves to `docs/legacy/PRD.v1.md`) |
| Audience | Antigravity agent (primary), engineers, regulatory product owners |
| Companion docs | `WORKFLOW.md` (how the agent operates + runtime flow), `ARCHITECTURE.md` (technical source of truth), `DESIGN.md` (UI/UX system), `PHASE_STATE.md` (live progress ledger the agent reads and writes) |
| Requirement IDs | `FR-*`, `NFR-*`, `AC-*`, `G-*` are **unchanged from v1** so existing code comments and tests stay valid. New IDs: `P{n}-T{nn}` (phase tasks), `P{n}-G{n}` (phase gate checks) |
| Keywords | `MUST` / `SHOULD` / `MAY` per RFC 2119 |

---

## 0. How this PRD is used (read first, agent)

1. The project is built in **8 phases**. Phase 8 is the final phase and ends in a tagged release.
2. **You only work on one phase at a time.** The human starts a phase by typing `start phase N` (or `next phase`). Nothing else starts a phase. Never roll into the next phase on your own, even if time remains.
3. Before doing anything on a phase, follow the **Session Start Ritual** in `WORKFLOW.md §A.2`: read `PHASE_STATE.md`, confirm phase N-1 is `COMPLETE` with passing gate evidence, load only the docs sections listed in that phase's *Read first* line.
4. Each phase in §5 is self-contained. It lists: objective, prerequisites, **what you need from the human (keys, data, links)**, ordered tasks, deliverables, acceptance criteria with copy-paste verification commands, an exit gate, and the exact handoff block you write into `PHASE_STATE.md`.
5. **Never invent credentials, URLs, dataset contents, or test results.** If something in a phase's *Human inputs* table is missing, follow the blocker protocol (`WORKFLOW.md §A.6`): stop that task, use the documented fallback if one exists, record the blocker, and ask once, clearly.
6. A phase is `COMPLETE` only when every exit-gate box is checked **with command output pasted into `PHASE_STATE.md`**. "Looks right" is not evidence.

---

## 1. Product summary

### 1.1 Mission
Compress the market-manipulation investigation lifecycle from **months to minutes** by fusing high-frequency order-book telemetry with public social/OSINT signals, unmasking coordinated trading syndicates, and compiling cryptographically signed, court-ready dossiers, **with a human investigator always in the decision loop**.

### 1.2 Stakeholders
Market regulators (SEBI, SEC), exchange surveillance desks (NSE, BSE, NASDAQ, NYSE), compliance officers, forensic investigators, legal counsel, platform SRE.

### 1.3 In scope
Real-time market ingestion (L2/L3/trades) and social/OSINT ingestion; quant anomaly detection; semantic parsing and hype scoring; cross-modal alignment; graph attribution of syndicates; LangGraph orchestration with a human review gate; signed dossier (PDF + JSON + bundle) and offline verifier; investigator web app; deterministic simulator; dataset replay; automated acceptance suite.

### 1.4 Out of scope
Trading or any action against participants (read-only analytics). Joining private channels or breaking encryption (public and lawful-access only). Automated accusations (outputs are *investigative leads with confidence*). Vendor exchange certification. Native mobile apps.

### 1.5 Binding guardrails (unchanged, enforced in code and tests)
- **G-1 Human in the loop:** nothing reaches `PUBLISHED` without an authenticated reviewer approval event.
- **G-2 Probabilistic attribution:** links carry `confidence`, `method`, `evidence_refs`; `< 0.60` is `INFERRED-LOW`, shown as *leads*, excluded from findings.
- **G-3 Pseudonymization:** account, handle, IP, device, KYC ids are keyed HMAC-SHA-256 pseudonyms; reveal is a privileged, audit-logged call.
- **G-4 Auditability:** every agent decision, LLM call (prompt hash + response hash) and human action is ledgered.
- **G-5 Data minimization:** social text retention default 180 days unless on legal hold.
- **G-6 (new) Honest data labelling:** any record that is simulated or contains synthetic overlay (for example real public prices with synthetic account ids) MUST carry `is_synthetic=true`. The UI shows a visible *Synthetic data* chip whenever a case contains such records. Dossiers generated from synthetic data MUST say so on the cover page.

---

## 2. Baseline audit of the uploaded repository (what already exists)

Audited from `VIGIL-main.zip` (about 4,570 lines of Python in `services/`, a Next.js 14 frontend). Treat this table as the starting truth. Phase 1 re-verifies it by running the code.

| Area | State found | Gap to close | Phase |
|---|---|---|---|
| Docs | `PRD.md`, `ARCHITECTURE.md` (97 KB), `FLOW.md`, `FRONTEND.md`, `README.md` (links point to a local Mac path) | Replace with v2 doc set; keep old ones in `docs/legacy/`; fix README links | 1 |
| `libs/vigil_common` | Present: schemas (7), models, hashing, canonical, merkle, ledger, signing, verifier, evidence, pseudonym, topics | Contract tests missing (`tests/contract/` does not exist but CI calls it) | 1 |
| Infra | `docker-compose.yml` (redpanda, redis, timescale, neo4j 5.24, minio, otel, prometheus, grafana), init scripts, one Alembic migration | Never booted in CI; Grafana dashboards are ~300-byte stubs; confirm GDS plugin | 1, 8 |
| Datasets | No `datasets/` directory; no dataset fetch logic; `AC-SOC-01` references `datasets/social_labeled_v1.jsonl` which does not exist | Build dataset layer that fetches from the human-provided GitHub repo | 1, 2, 3 |
| `simulator` | Substantial: market model, order book, ring, social model, 6 scenario YAMLs, ground truth, server | Determinism and ground-truth tests; replay adapter | 2 |
| `market_ingest` / `stream_sink` | Implemented (162 / 326 lines) | Hardening: DLQ, seq-gap, dedupe, overload shedding, raw archive hashing, load test | 2 |
| `quant_telemetry` | One 253-line file | Verify all six detectors against FR-QTA-01..08, hot reload, warm restart | 2 |
| `social_ingest` / `social_intel` | Implemented (142 / 282 lines) | LLM path, MinHash-LSH, CTA fallback classifier, corpus-based F1 tests | 3 |
| `alignment_engine` | 217 lines | Permutation test rigor, MRS, watermark, calibration | 4 |
| `attribution` | 254 lines | Cypher cycle/community queries, KS/reaction tests, entity ring score, feedback veto | 5 |
| `orchestrator` | `CaseOrchestrator` class over Kafka; **`langgraph` is declared in `pyproject.toml` but not imported** | Real LangGraph `StateGraph`, `PostgresSaver`, interrupt gate, Redis-Streams tool bus | 6 |
| `evidence_engine` | `main.py` is an idle loop; `builder.py` (278 lines) plus `vigil_common/evidence.py` | Capture, ledger triggers, Merkle, JCS, signing, WeasyPrint PDF, bundle, anchoring | 6 |
| `verifier` | `core.py` + CLI (141 lines total) | Full 6-check coverage and tamper tests | 6 |
| `api` | 753-line `main.py` (single file) | Split into routers, RBAC, RFC 7807, rate limits, WS fan-out | 7 |
| `frontend` | Routes and ~25 components exist; `tokens.css`, Tailwind config. Some components (Heatmap, ReviewPanel) still use ad-hoc `slate-950` classes that bypass the tokens. `src/lib/` is missing (api client, format, copy) | Implement `DESIGN.md`, add `lib/`, remove token bypasses, Tape polish, a11y, Playwright | 7 |
| Tests | Only `tests/unit/test_simulator.py` | Unit, contract, integration, e2e, load, chaos | 1 to 8 |
| CI | Lint, mypy (libs only), unit tests | Add services typing, contract, integration (compose), frontend build, e2e, security scans | 1, 8 |

---

## 3. Global registry: keys, data, links, and where each goes

> The agent MUST consult this registry whenever a task needs a secret, dataset, or external reference. Values are never committed. They live in `.env` (git-ignored) and are listed here only by name.

### 3.1 Keys and credentials

| Name (`.env`) | Needed from phase | Required? | Where the human gets it | Fallback if absent |
|---|---|---|---|---|
| `DATASET_REPO_URL` | 1 | **Required for dataset-backed work** | **The GitHub repo URL the human provides.** Not present in the uploaded zip; the agent MUST ask for it at the start of Phase 1 and record it in `PHASE_STATE.md` | Simulator-only mode (all synthetic). Phases 1 to 8 still pass their gates, but `AC-SOC-01` and replay tests run on simulator-generated corpora |
| `DATASET_REPO_REF` | 1 | Optional | Branch, tag or commit of that repo. Default `main`. **Pin to a commit SHA once the human confirms** | `main` |
| `GITHUB_TOKEN` | 1 | Only if the dataset repo is private | https://github.com/settings/tokens (fine-grained, read-only contents on that one repo) | Public clone only |
| `ANTHROPIC_API_KEY` | 3 | Optional | https://console.anthropic.com/settings/keys | System runs in `FALLBACK_RULES` and `TEMPLATE` modes (AC-SOC-02, AC-ORC-03) |
| `LLM_MODEL` | 3 | Optional | Default `claude-sonnet-5-5`; models list at https://docs.claude.com/en/docs/about-claude/models | n/a |
| `SIGNING_KEY_PATH` / `SIGNING_KEY_ID` | 6 | Auto | Generated by `scripts/gen_dev_keys.sh` (Ed25519). Never commit `keys/*.pem` | n/a |
| `PSEUDONYM_PEPPER` | 1 | Auto (dev) | Dev default in `.env.example`. Production: KMS/Vault | n/a |
| `JWT_HS256_SECRET` | 7 | Auto (dev) | Any 32+ byte random string (`openssl rand -hex 32`) | n/a |
| `OIDC_ISSUER`, `OIDC_CLIENT_ID` | 7 / 8 | Optional | Identity provider of the deployment | HS256 dev issuer, disabled when `ENV=prod` |
| `TSA_URL` | 6 | Optional | An RFC 3161 time-stamp authority, for example https://freetsa.org/tsr (public test TSA; verify availability) | Daily anchor without TSA token |
| `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` | 3 | Optional, off by default | https://my.telegram.org (API development tools). **Public channels only** (FR-SOC-08) | Synthetic and file-replay adapters |
| `S3_*`, `PG_DSN`, `NEO4J_*`, `REDIS_URL`, `KAFKA_BOOTSTRAP` | 1 | Auto | Defaults in `.env.example` match `docker-compose.yml` | n/a |

### 3.2 Datasets

All datasets are fetched by **one mechanism** (defined in Phase 1, `P1-T07..T10`): `make datasets`, which reads `datasets/manifest.yaml`, clones the repo at `DATASET_REPO_URL@DATASET_REPO_REF` using a shallow sparse checkout, copies the listed paths into `datasets/data/`, and verifies each file's SHA-256 against the manifest. The agent never hand-edits files in `datasets/data/`.

| Logical dataset | Used in | Expected form | Source |
|---|---|---|---|
| `market_trades` | 2 | CSV/Parquet/NDJSON of trades (`ts, price, qty, side`) | Human's dataset repo |
| `market_l2` (optional) | 2 | L2 snapshots or LOB messages | Human's dataset repo |
| `social_messages` | 3 | JSONL (`platform, channel, author, ts, text`) | Human's dataset repo |
| `social_labeled_v1` | 3 | JSONL, **≥ 500 rows**, labels: `tickers[]`, `cta` | Human's repo; if absent, the agent generates a *draft* from the simulator and marks it `needs_human_review` (AC-SOC-01 then reports on a synthetic corpus and says so) |
| `ground_truth_cases` (optional) | 4, 5 | JSON listing known manipulation windows/accounts | Human's repo |

**Public candidates the human may add to their dataset repo** (the agent must not download these on its own, and must tell the human to verify licenses before use): Binance public market data at https://data.binance.vision (trades/klines, CC-style public terms, no account identities); LOBSTER sample files at https://lobsterdata.com/info/DataSamples.php (L3-style NASDAQ message data samples); FI-2010 limit-order-book benchmark (Fairdata, Finland). Public market data has **no trader identities**, so any use for graph work requires a synthetic identity overlay, which triggers guardrail **G-6**.

### 3.3 Reference links (agent may open these; do not copy long passages, summarize)

| Topic | Link |
|---|---|
| RFC 8785 JSON Canonicalization | https://www.rfc-editor.org/rfc/rfc8785 |
| RFC 6962 Merkle hash trees (domain separation) | https://www.rfc-editor.org/rfc/rfc6962 |
| RFC 8032 Ed25519 | https://www.rfc-editor.org/rfc/rfc8032 |
| RFC 3161 Time-stamp protocol | https://www.rfc-editor.org/rfc/rfc3161 |
| RFC 7807 Problem Details | https://www.rfc-editor.org/rfc/rfc7807 |
| LangGraph (state graph, checkpointing, interrupts) | https://langchain-ai.github.io/langgraph/ |
| Redpanda | https://docs.redpanda.com/ |
| TimescaleDB | https://docs.timescale.com/ |
| Neo4j Cypher + GDS | https://neo4j.com/docs/ |
| WeasyPrint | https://doc.courtbouillon.org/weasyprint/ |
| Cytoscape.js | https://js.cytoscape.org/ |
| Anthropic API docs | https://docs.claude.com |
| SEBI PFUTP Regulations, 2003 | https://www.sebi.gov.in (Legal framework → Regulations) |
| SEC Exchange Act §9, §10(b), Rule 10b-5 | https://www.sec.gov/ |
| OWASP ASVS | https://owasp.org/www-project-application-security-verification-standard/ |
| WCAG 2.2 | https://www.w3.org/TR/WCAG22/ |

### 3.4 Ports and local URLs

Dashboard `http://localhost:3000` · API + docs `http://localhost:8000/docs` · Simulator `:8090` · Redpanda Console `:8080` · Neo4j Browser `:7474` · MinIO Console `:9001` · Grafana `:3001` (check compose) · Prometheus `:9090`.

---

## 4. Phase map at a glance

| # | Phase | Outcome (one sentence) | Primary requirement IDs | Gate command |
|---|---|---|---|---|
| 1 | **Foundation, Infra & Data Layer** | Clean repo, full stack boots, contracts tested, datasets fetch from the human's GitHub repo, CI is meaningful | NFR-INT-02, NFR-SEC-06, §4.5 | `make gate PHASE=1` |
| 2 | **Market Telemetry** | Simulator + dataset replay → ingest → sink → six quant detectors, measured against ground truth | FR-MKT-*, FR-QTA-* | `make gate PHASE=2` |
| 3 | **Social Intelligence** | Social ingest, ticker/CTA parsing (LLM + fallback), near-dup, hype score and bursts | FR-SOC-* | `make gate PHASE=3` |
| 4 | **Cross-Modal Alignment & MRS** | Social leads market is detected with a permutation test; MRS per minute; case trigger | FR-ALN-* | `make gate PHASE=4` |
| 5 | **Graph Attribution** | Neo4j graph, link methods, rings, entities, investigator feedback, Cytoscape export | FR-GRA-* | `make gate PHASE=5` |
| 6 | **Orchestration & Evidence** | Real LangGraph case machine; signed dossier, ledger, Merkle, PDF, bundle, offline verifier | FR-ORC-*, FR-DOS-* | `make gate PHASE=6` |
| 7 | **API & Investigator UI** | Complete REST/WS API with RBAC; the full UI per `DESIGN.md`; Playwright + a11y | FR-API-*, FR-UI-* | `make gate PHASE=7` |
| 8 | **Hardening & Release (final)** | Load, chaos, security, observability, docs, demo, `v1.0.0` tag | NFR-* | `make gate PHASE=8` |

`make gate PHASE=n` is created in **P1-T14**. It runs that phase's verification script (`scripts/gates/phase_n.sh`) and prints a pass/fail table the agent pastes into `PHASE_STATE.md`.

**Dependency chain:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Phases 2 and 3 are logically parallel but are built in order so the Alignment phase has both inputs. Phase 7's UI can use mock data earlier, but its acceptance needs the real stack from phases 2 to 6.

---

## 5. The eight phases

Each phase follows the same template. Task IDs are stable; reference them in commit messages (`P3-T05: ...`).

---

### PHASE 1 — Foundation, Infrastructure & Data Layer

**Objective.** Make the repository trustworthy: documentation replaced, every service boots, schemas are contract-tested, CI actually exercises the code, and the **dataset layer** can pull data from the human's GitHub repository.

**Read first:** `ARCHITECTURE.md` §2 (stack), §4 (data plane), §12 (deployment), §14 (CI); `WORKFLOW.md` §A.

**Prerequisites:** none (first phase). Docker ≥ 25 with Compose v2, Python 3.12 via `uv`, Node ≥ 20 via `pnpm`.

**Human inputs**

| Item | Blocker? | Action if missing |
|---|---|---|
| `DATASET_REPO_URL` (+ optional `DATASET_REPO_REF`, `GITHUB_TOKEN`) | Blocks `P1-T08..T10` only | Ask once: *"Please paste the GitHub URL of your dataset repo, the branch or commit to pin, and tell me if it is private."* Meanwhile continue other tasks; set `DATASET_MODE=synthetic` |
| Confirmation of the dataset repo's directory layout | Soft | The agent lists the repo tree after the first clone and proposes `datasets/manifest.yaml`; human confirms |

**Tasks**

| ID | Task | Detail |
|---|---|---|
| P1-T01 | Archive legacy docs | `git mv PRD.md docs/legacy/PRD.v1.md`, same for `ARCHITECTURE.md`, `FLOW.md`, `FRONTEND.md`. Install the v2 set (`PRD.md`, `WORKFLOW.md`, `ARCHITECTURE.md`, `DESIGN.md`, `PHASE_STATE.md`) at the repo root |
| P1-T02 | Fix README | Replace the absolute `file:///Users/...` links with relative links to the new docs; add the 8-phase table and `start phase N` instructions |
| P1-T03 | Baseline run | `uv sync --all-packages`, `make lint`, `make test`; record every failure in `PHASE_STATE.md` under *Known issues*. Fix those that block later phases now |
| P1-T04 | Boot the stack | `make up`; fix compose problems. Confirm Redpanda topics (`infra/redpanda/create_topics.sh`), Timescale migration `0001`, Neo4j constraints, MinIO buckets. Verify Neo4j GDS availability: if `NEO4J_PLUGINS` lacks `graph-data-science`, add it, else document the NetworkX fallback path |
| P1-T05 | Contract tests | Create `tests/contract/`. For each of the 7 schemas in `libs/vigil_common/schemas/`: one valid fixture, ≥ 3 invalid fixtures (missing field, bad pattern, extra property). `scripts/export_schemas.py --check` must show no drift |
| P1-T06 | Test scaffolding | Create `tests/integration/`, shared fixtures (Kafka/Timescale test containers via compose profile `test`), `tests/conftest.py`, coverage config (`--cov-fail-under` ramps: 40 % now, 80 % by Phase 8) |
| P1-T07 | Dataset manifest | Create `datasets/manifest.yaml` (format in `ARCHITECTURE.md §3.6`): logical name → repo path → SHA-256 → license note → `is_synthetic` → target schema. Create `datasets/README.md`. Add `datasets/data/` to `.gitignore` |
| P1-T08 | Fetch script | `scripts/fetch_datasets.sh` (and `make datasets`): shallow, sparse clone of `$DATASET_REPO_URL` at `$DATASET_REPO_REF` into a temp dir; copy only manifest paths; verify SHA-256; refuse on mismatch; write `datasets/data/.fetch_receipt.json` (repo URL, **resolved commit SHA**, timestamp, per-file hashes). If `GITHUB_TOKEN` is set use it via `GIT_ASKPASS`, never in the URL. Exit code 2 with a clear message if the URL is unset |
| P1-T09 | Dataset loader lib | `libs/vigil_common/src/vigil_common/datasets.py`: typed `DatasetRegistry`, `open_dataset(name)` iterators (CSV, Parquet, JSONL, NDJSON.zst), schema mapping hooks. Unit-tested with tiny fixtures committed under `tests/fixtures/datasets/` |
| P1-T10 | Dataset-in-CI policy | CI never needs the human's repo. It uses fixtures. A separate manual workflow `datasets-check.yml` (workflow_dispatch) runs `make datasets` with a repo secret |
| P1-T11 | Env and secret hygiene | `.env.example` gains `DATASET_REPO_URL`, `DATASET_REPO_REF`, `DATASET_MODE=auto|synthetic|repo`, `GITHUB_TOKEN`. Add `gitleaks` pre-commit and CI step. Confirm `.gitignore` covers `.env`, `keys/*.pem`, `datasets/data/` |
| P1-T12 | CI upgrade | Jobs: lint+mypy (`libs` **and** `services`), unit+contract, `docker compose config -q`, frontend `pnpm install && pnpm build`, gitleaks. Cache uv and pnpm |
| P1-T13 | Observability skeleton | Fill the three Grafana dashboards (`ingest`, `agents`, `cases`) with real panels bound to the metric names in `ARCHITECTURE.md §10`; metrics may be empty until later phases |
| P1-T14 | Gate harness | `scripts/gates/phase_1.sh … phase_8.sh` (phase 1 real, others stubs that exit 99 "not implemented") and `make gate PHASE=n`. Gate scripts print a markdown table of checks |
| P1-T15 | Initialize `PHASE_STATE.md` | Fill *Environment*, *Dataset receipt*, *Known issues*, and mark Phase 1 `COMPLETE` only after the gate passes |

**Deliverables:** v2 docs installed; `datasets/` layer; `scripts/fetch_datasets.sh`; `scripts/gates/*`; `tests/contract/*`; upgraded CI; populated Grafana dashboards; updated README.

**Acceptance criteria**

| ID | Criterion | Verify |
|---|---|---|
| P1-G1 | `make up` brings every container to healthy within 5 min on the reference machine | `make up && ./scripts/wait_for_stack.sh; echo $?` → `0` |
| P1-G2 | All 7 schemas have valid + invalid fixtures; export is drift-free | `uv run pytest tests/contract -q` and `uv run python scripts/export_schemas.py --check` |
| P1-G3 | `ruff` and `mypy --strict` clean for `libs` and `services` | `make lint` |
| P1-G4 | With `DATASET_REPO_URL` set, `make datasets` fetches, verifies and writes a receipt including the resolved commit SHA. With it unset, exits 2 with guidance | `make datasets; cat datasets/data/.fetch_receipt.json` |
| P1-G5 | Tampering with one fetched byte makes the next verify fail | `scripts/fetch_datasets.sh --verify-only` after `echo x >> datasets/data/<file>` → non-zero |
| P1-G6 | CI is green on a clean clone using fixtures only | GitHub Actions run URL pasted into `PHASE_STATE.md` |
| P1-G7 | No secrets in git history of this repo | `gitleaks detect --no-banner` → no leaks |

**Exit gate:** P1-G1..G7 checked and evidence pasted; `PHASE_STATE.md` Phase 1 = `COMPLETE`.

**Handoff block to write:** repo layout confirmation; the dataset receipt (commit SHA, file hashes); list of datasets actually present vs `simulator-only`; Neo4j GDS decision; the exact `make` targets that now exist; any deferred issues with owner phase.

---

### PHASE 2 — Market Telemetry: Simulator, Replay, Ingest, Sink, Quant Detectors

**Objective.** Produce a trustworthy market data plane and six detectors whose precision and recall are *measured* against simulator ground truth (and against labelled windows from the dataset repo if provided).

**Read first:** `ARCHITECTURE.md` §4.1, §4.3, §5 (data plane), §8.1 (detectors and formulas), §3.6 (datasets); PRD FR-MKT, FR-QTA; v1 AC-ING, AC-QTA.

**Prerequisites:** Phase 1 `COMPLETE`.

**Human inputs**

| Item | Blocker? | Fallback |
|---|---|---|
| `market_trades` (and optionally `market_l2`) in the dataset repo | No | Simulator-only; replay tests use fixtures |
| Column mapping for the human's files (timestamp format and timezone, side encoding, price scale) | Yes for replay | The agent infers from the first 20 rows and **asks the human to confirm the mapping** before writing the adapter's defaults |
| Ground-truth windows (optional) | No | Simulator labels only |

**Tasks**

| ID | Task | Detail |
|---|---|---|
| P2-T01 | Simulator determinism | Same `scenario + seed` ⇒ byte-identical event stream (hash of NDJSON). Add `tests/unit/test_sim_determinism.py` and ground-truth export (`ground_truth_out`) |
| P2-T02 | Scenario completeness | Verify the six YAMLs: `baseline_01`, `pump_dump_ring_01`, `wash_ring_01`, `spoofing_01`, `liquidity_squeeze_01`, `adversarial_noise_01`. Each emits `scenario_label` only in the ground-truth side channel, stripped from agent input (schema `scenario_label` rule) |
| P2-T03 | `FileReplayAdapter` | Replay NDJSON/CSV/Parquet at speed ×1…×1000 preserving inter-arrival times; `DatasetTradeAdapter` maps the human's columns to `TradeTick`. If the data lacks accounts, apply a **seeded synthetic identity overlay** and set `is_synthetic=true` (G-6) |
| P2-T04 | `market_ingest` hardening | JSON-Schema validate every event; failures → `dlq.market` with `{original_b64,error,stage,ts}` (FR-MKT-03); per-symbol `seq` check → `SEQ_GAP` health event (FR-MKT-04); `ts_ingest` + `ingest_latency_us` (FR-MKT-05); 10-min Redis dedupe (FR-MKT-06); partition key `symbol` |
| P2-T05 | Overload policy | At `INGEST_QUEUE_HIGH_WATERMARK`, shed **only L2 deltas**, count in `vigil_overload_shed_total`, never drop trades/L3 (NFR-HA-04) |
| P2-T06 | Raw archive | `stream_sink` writes `vigil-raw/market/YYYY/MM/DD/HH/*.ndjson.zst` with hourly SHA-256 rollup into the ledger (FR-MKT-07) |
| P2-T07 | Timescale writers | Batch `COPY` into `trades`, `l2_snapshots`, `bars_1s`, depth metrics (FR-MKT-08). Idempotent upsert keys so replays don't duplicate (AC-ING-04) |
| P2-T08 | Detectors | Implement/verify: `VolumeSpikeDetector`, `SpreadDepthDetector`, `SpoofingLayeringDetector`, `WashCycleDetector`, `SynchronizedOrdersDetector`, `PriceJumpDetector` per formulas in `ARCHITECTURE.md §8.1`. Every anomaly has `score`, `severity`, `metrics`, `evidence_refs` (FR-QTA-07) |
| P2-T09 | Config + state | `config/detectors.yaml` per tier (micro/mid/large), hot-reload on file change (FR-QTA-08); warm-restart snapshots to `state:qta:{symbol}` |
| P2-T10 | Evaluation harness | `scripts/eval_detectors.py` runs each scenario × seeds 1–5 and writes `reports/qta_eval.md` with precision/recall per detector vs ground truth. Commit the report |
| P2-T11 | Metrics | `vigil_ingest_latency_seconds{stream}`, `vigil_detect_latency_seconds`, `vigil_dlq_total{reason}`, `vigil_dedupe_total` |
| P2-T12 | Phase tests | Unit tests ≥ 80 % on `quant_telemetry`; integration test that boots ingest+sink+QTA against compose and replays `baseline_01` |

**Deliverables:** deterministic simulator; replay adapters; hardened ingest and sink; six detectors; `reports/qta_eval.md`; gate script `phase_2.sh`.

**Acceptance criteria**

| ID | Criterion | Verify |
|---|---|---|
| AC-ING-01 | `baseline_01`, 10 simulated min, 5,000 ev/s → 0 DLQ, p99 ingest latency < 200 ms | `make scenario ID=baseline_01 SPEED=10 SEED=42` then `scripts/gates/phase_2.sh ing01` |
| AC-ING-02 | 100 malformed events → exactly 100 DLQ records with non-empty `error` | `uv run pytest tests/integration/test_dlq.py` |
| AC-ING-03 | Injected sequence gap → one `SEQ_GAP` within 2 s | `pytest tests/integration/test_seq_gap.py` |
| AC-ING-04 | Replaying the same file twice leaves `trades` row count unchanged | `pytest tests/integration/test_idempotent_replay.py` |
| AC-QTA-01 | `pump_dump_ring_01` yields `VOLUME_SPIKE` and `PRICE_JUMP` on the target; `baseline_01` yields none (seeds 1–5) | `uv run python scripts/eval_detectors.py --check` |
| AC-QTA-02 | `wash_ring_01`: ≥ 90 % of injected cycles detected, precision ≥ 0.8 | same |
| AC-QTA-03 | `spoofing_01`: recall ≥ 0.9 per injected spoofer | same |
| P2-G1 | If a human dataset is present: replay of `market_trades` produces valid `TradeTick`s with 0 DLQ (excluding rows the report lists as malformed) | `make replay DATASET=market_trades SPEED=100` |
| P2-G2 | Determinism hash test passes | `pytest tests/unit/test_sim_determinism.py` |

**Exit gate:** all above + `make gate PHASE=2` prints PASS; `reports/qta_eval.md` committed.

**Handoff block:** detector thresholds actually used; eval table; which datasets were replayed and their column mapping (so Phase 3/4 don't re-derive it); known detector weaknesses; latency numbers.

---

### PHASE 3 — Social Intelligence: Ingest, Semantic Parsing, Hype Scoring

**Objective.** Turn raw multilingual chat (English, Hinglish) into ticker-resolved, CTA-classified, deduplicated signals and a 5-second `hype_score` with burst events, working **with or without** an LLM.

**Read first:** `ARCHITECTURE.md` §4.2, §8.2 (hype formula), §3.6; FR-SOC-*; DESIGN.md §10 (copy rules for social text display).

**Prerequisites:** Phase 2 `COMPLETE`.

**Human inputs**

| Item | Blocker? | Fallback |
|---|---|---|
| `ANTHROPIC_API_KEY` | No | `FALLBACK_RULES` mode (rules + multilingual embedding nearest-centroid). AC-SOC-02 proves this |
| `social_messages` and `social_labeled_v1` in the dataset repo | Soft | Simulator corpus; the agent produces `datasets/data/social_labeled_v1.draft.jsonl` and asks the human to review a random sample of 50 rows before it is treated as ground truth |
| Telegram API credentials | No | `TelegramPublicChannelAdapter` stays disabled |
| Confirmation of the ticker alias list for the target exchange(s) | Soft | Use `config/ticker_aliases.yaml` as is |

**Tasks**

| ID | Task | Detail |
|---|---|---|
| P3-T01 | Adapters | `SyntheticTelegramAdapter`, `FileReplayAdapter`, `TelegramPublicChannelAdapter` (Telethon, **disabled by default**, public channels only). Visibility gate: only `public` or `lawful_access`; others → `dlq.social` reason `VISIBILITY_NOT_PERMITTED` (FR-SOC-08) |
| P3-T02 | Pseudonymize + dedupe | Handles/ids → HMAC pseudonyms; dedupe on `(platform, channel_id, message_id)`; keep `raw_sha256` (FR-SOC-02, 07) |
| P3-T03 | Text normalization | NFKC, emoji handling, Devanagari and Hinglish transliteration helper, URL/mention stripping that preserves cashtags |
| P3-T04 | Ticker extraction | Cashtags, bare tickers, company names and aliases with per-mention confidence (FR-SOC-03). Ambiguity rules: a bare token that is also an English word needs a corroborating cue |
| P3-T05 | CTA classifier — fallback | Rules + lexicon (`config/cta_lexicon.yaml`) + nearest-centroid on a multilingual sentence embedding (ship a small model choice documented in ARCHITECTURE; offline-capable). Classes: `BUY_CALL, HOLD_PUMP, TARGET_PRICE, EXIT_SIGNAL, COORDINATION_TIMING, NEUTRAL` |
| P3-T06 | CTA classifier — LLM path | Async, bounded by `LLM_MAX_CONCURRENCY`, `LLM_TIMEOUT_S`; structured output validated by Pydantic; on any failure fall back to P3-T05 and tag `parser_mode`. Ledger stores prompt hash + response hash, not text unless `LLM_TRACE_STORE_TEXT=true` (G-4) |
| P3-T07 | Near-dup / coordination | MinHash-LSH (Jaccard ≥ 0.8 within 5 min across channels), forward cascades, synchronized posting → `near_dup_cluster_id` (FR-SOC-05) |
| P3-T08 | Hype scorer | Implement the formula in `ARCHITECTURE.md §8.2` with weights from `config/hype_weights.yaml`; 60-s window, 5-s step; `N<5 ⇒ cap 20`; emit `HYPE_BURST` at ≥ 70 for ≥ 30 s and `NEAR_DUPLICATE_CAMPAIGN` |
| P3-T09 | Corpus + evaluation | Build `scripts/eval_social.py`: ticker F1, CTA macro-F1 on `social_labeled_v1` in both modes; writes `reports/social_eval.md` |
| P3-T10 | Persistence | `social_signals`, `hype_5s` hypertable writers in `stream_sink`; retention job (G-5) |
| P3-T11 | Phase tests | Unit ≥ 80 % on `social_intel`; integration: scenario replay produces `HYPE_BURST` |

**Acceptance criteria**

| ID | Criterion | Verify |
|---|---|---|
| AC-SOC-01 | Ticker F1 ≥ 0.92 and CTA macro-F1 ≥ 0.80 in LLM mode; ≥ 0.85 and ≥ 0.70 in fallback mode, on the labelled corpus (≥ 500 rows). The report states whether the corpus is human-labelled or synthetic-draft | `uv run python scripts/eval_social.py --check` |
| AC-SOC-02 | With `ANTHROPIC_API_KEY` empty the pipeline runs and every signal has `parser_mode=FALLBACK_RULES` | `pytest tests/integration/test_social_fallback.py` |
| AC-SOC-03 | `pump_dump_ring_01`: `HYPE_BURST` for `ZENITHSME` within 60 s of the first coordinated message | `make scenario ID=pump_dump_ring_01 SPEED=10 SEED=42` + `scripts/gates/phase_3.sh soc03` |
| P3-G1 | Non-public visibility is rejected with the exact DLQ reason | `pytest tests/integration/test_visibility_gate.py` |
| P3-G2 | LLM calls honor timeout and concurrency bounds (fault-injected) | `pytest tests/unit/test_llm_bounds.py` |
| P3-G3 | No raw handle or message id appears in any stored row | `pytest tests/integration/test_pseudonymization.py` |

**Exit gate:** all checked; `reports/social_eval.md` committed with both modes' numbers.

**Handoff block:** which mode produced the committed numbers; embedding model name/version/size; corpus provenance and review status; prompt version hash; hype weights; known failure cases (code-mixed text, sarcasm).

---

### PHASE 4 — Cross-Modal Alignment & Manipulation Risk Score

**Objective.** Detect when social hype leads market activity, quantify it with a permutation test, score every ticker every minute (MRS), and open cases.

**Read first:** `ARCHITECTURE.md` §8.3, §8.4; FR-ALN-*; `WORKFLOW.md §B` stages S6–S7.

**Prerequisites:** Phase 3 `COMPLETE` (both anomaly streams exist).

**Human inputs:** optional `ground_truth_cases` (known pump windows) for calibration. No keys needed.

**Tasks**

| ID | Task | Detail |
|---|---|---|
| P4-T01 | Series assembly | Per ticker 1-s grid over last `ALIGN_LOOKBACK_S`: `h(t)`, `v(t)` (robust-z of `bars_1s`, log1p, detrended by 5-min rolling median), `a(t)` = abs return, `spread_rel` (FR-ALN-01) |
| P4-T02 | Cross-correlation | FFT normalized xcorr for lags −120…+1800 s; `best_lag_s`, `xcorr_peak`; positive lag = social leads (FR-ALN-02) |
| P4-T03 | Permutation test | Circular block shuffle (60 s blocks), B=500 (1000 in case-run), `p=(1+#{null≥obs})/(B+1)`; seeded RNG from `(symbol, window)` for reproducibility (NFR-INT-02) |
| P4-T04 | Event fast path | `HYPE_BURST` followed by `VOLUME_SPIKE|PRICE_JUMP` within 15 min qualifies without the test (FR-ALN-03) |
| P4-T05 | Watermark | 30-s event-time watermark; series recomputed from Timescale each cycle so late data counts (FR-ALN-05) |
| P4-T06 | MRS | Per ticker per minute, formula in `ARCHITECTURE.md §8.4`, components persisted in `mrs_1m.components`, latest in Redis `mrs:{symbol}` (TTL 120 s) (FR-ALN-04) |
| P4-T07 | Case trigger | Publish `CROSS_MODAL_ALIGNMENT` to `anomaly.fused` and `CaseTrigger` to `case.trigger`; update `watchlist:symbols` |
| P4-T08 | Calibration report | Sweep thresholds over seeds 1–5 (all scenarios); `reports/alignment_eval.md` with ROC-style table and the chosen operating point; if a human ground-truth file exists include it |
| P4-T09 | Performance | One alignment cycle for 50 tickers < 1 s CPU budget per ticker average; benchmark committed |

**Acceptance criteria**

| ID | Criterion | Verify |
|---|---|---|
| AC-ALN-01 | `pump_dump_ring_01`: alignment emitted, `best_lag_s` within ±30 s of the simulator's configured reaction lag (mean 150 s) | `scripts/gates/phase_4.sh aln01` |
| AC-ALN-02 | `baseline_01`: no case opened over 30 simulated min, seeds 1–5 | `scripts/gates/phase_4.sh aln02` |
| P4-G1 | Same inputs + same seed ⇒ identical `p_value` and lag (determinism) | `pytest tests/unit/test_alignment_determinism.py` |
| P4-G2 | Late social message (≤ 30 s) changes the series and is reflected next cycle | `pytest tests/integration/test_watermark.py` |
| P4-G3 | MRS component weights sum to 1.00 and each component is in [0,1] | `pytest tests/unit/test_mrs.py` |

**Exit gate:** AC + P4-G1..G3 + `reports/alignment_eval.md`.

**Handoff block:** operating thresholds and why; false-positive notes from `adversarial_noise_01`; MRS sample values for the demo scenario (the UI uses them in Phase 7).

---

### PHASE 5 — Graph Attribution: Rings, Entities, Investigator Feedback

**Objective.** Build the Neo4j entity graph, link accounts with explainable multi-method evidence, detect circular rings and coordinated volume, resolve entities with a ring score, and accept investigator feedback.

**Read first:** `ARCHITECTURE.md` §7 (graph model + Cypher), §8.5 (link evidence, ring score); FR-GRA-*; guardrails G-2, G-3.

**Prerequisites:** Phase 4 `COMPLETE`.

**Human inputs:** none required. Optional: `ground_truth_cases` listing true ring members for the human's dataset (otherwise simulator ground truth). Confirm the Neo4j GDS decision recorded in Phase 1.

**Tasks**

| ID | Task | Detail |
|---|---|---|
| P5-T01 | Loader + writer | Loader turns normalized trades/orders/signals into `GraphUpdate`s on `graph.updates`; writer applies them idempotently with `MERGE`. Watchlist-gated so only symbols of interest are materialized |
| P5-T02 | Link methods | Implement all eight methods with weights from `config/attribution_weights.yaml`: `SHARED_KYC, SHARED_DEVICE, CIRCULAR_CYCLE, SYNCHRONIZED_ORDERS, SHARED_NETWORK, LATENCY_SIGNATURE (KS, ≥ 50 samples), REACTION_LATENCY (Mann-Whitney vs 200 random reference times), BROKER_PATHWAY` |
| P5-T03 | Noisy-OR confidence | `conf_ij = 1 − Π(1 − w_m·s_m)`; create `LINKED` at ≥ 0.60; below → `INFERRED-LOW` leads |
| P5-T04 | Cycle query | Directed cycles length 2–6 with ≈ 0 net position change (FR-GRA-04) |
| P5-T05 | Communities | Louvain/WCC (GDS if available, else NetworkX) over `SYNCHRONIZED_WITH` + `SHARES_FINGERPRINT`; flag if combined volume ≥ 25 % of symbol volume (FR-GRA-05) |
| P5-T06 | Social-to-trader | `REACTED_TO` via reaction-latency analysis; direct handle→trader `LINKED_TO` only from lawful-access data with `method` (FR-GRA-06) |
| P5-T07 | Entities and ring score | Resolve clusters → `Entity` with `ring_score` per `ARCHITECTURE.md §8.5` (FR-GRA-08) |
| P5-T08 | Feedback | `CONFIRM` sets `conf=max(conf,0.95)`; `REJECT` deletes the edge **and stores a veto** so it is never recreated; both ledgered (FR-GRA-07) |
| P5-T09 | Export | `GET`-ready Cytoscape elements JSON, `max_nodes`, `min_conf` filters (FR-GRA-09) |
| P5-T10 | Degraded modes | Neo4j down → buffer on `graph.updates` (7 d), run SQL+NetworkX attribution, flag `ATTRIBUTION_SQL_ONLY` |
| P5-T11 | Evaluation | `scripts/eval_graph.py`: ring recovery precision/recall vs ground truth; `reports/graph_eval.md` |

**Acceptance criteria**

| ID | Criterion | Verify |
|---|---|---|
| AC-GRA-01 | `pump_dump_ring_01` (20 accounts, 3 brokers, 5 devices, 1 ASN): recover ≥ 18 of 20 ring accounts in one entity with precision ≥ 0.9 | `uv run python scripts/eval_graph.py --check` |
| AC-GRA-02 | Cycle query returns all injected cycles (length 2–5), none on `baseline_01` | `pytest tests/integration/test_cycles.py` |
| AC-GRA-03 | Graph API export p95 < 800 ms (N=100) for the demo case | `scripts/gates/phase_5.sh gra03` |
| P5-G1 | A rejected link is never recreated after a re-run (veto test) | `pytest tests/integration/test_feedback_veto.py` |
| P5-G2 | Links `< 0.60` never appear in `findings`, only `leads` | `pytest tests/unit/test_leads_vs_findings.py` |
| P5-G3 | Killing Neo4j for 60 s loses no graph updates after recovery (count reconciliation) | `scripts/chaos_test.sh neo4j` |

**Exit gate:** all checked; `reports/graph_eval.md` committed.

**Handoff block:** final weights; per-method contribution on the demo case; GDS vs NetworkX decision; known graph-size limits; sample Cytoscape JSON path for the UI.

---

### PHASE 6 — Orchestration & Evidence Engine

**Objective.** Replace the ad-hoc orchestrator with a real **LangGraph** state machine, then build the evidence engine that produces a signed, hash-chained, offline-verifiable dossier with a human review gate.

**Read first:** `ARCHITECTURE.md` §6 (state machine), §8.6 (case confidence), §8.7 (clause registry), §10 (evidence engine); FR-ORC-*, FR-DOS-*; guardrail G-1, G-4.

**Prerequisites:** Phase 5 `COMPLETE`.

**Human inputs**

| Item | Blocker? | Fallback |
|---|---|---|
| `ANTHROPIC_API_KEY` | No | `TemplateNarrator` (AC-ORC-03) |
| Jurisdiction choice(s) for clause mapping (`SEBI`, `SEC`) | Soft | Both; each flagged `legal_review_required: true` |
| `TSA_URL` | No | Anchor without TSA |
| Legal counsel review of the certificate-of-integrity template | **Human task, not agent** | The agent leaves the template marked `DRAFT — legal review required` |

**Tasks**

| ID | Task | Detail |
|---|---|---|
| P6-T01 | LangGraph graph | `services/agents/orchestrator/graph.py`: `StateGraph(CaseState)` with nodes `open_case, enrich, align, attribute, assess, draft, validate, sign, await_review, publish` and conditional edges per the state diagram. Remove the legacy class once parity tests pass |
| P6-T02 | Checkpointing | `PostgresSaver` with `thread_id=case_id`; crash/resume test; idempotency keys `sha256(case_id|node|attempt_group|canonical(inputs))` (FR-ORC-02) |
| P6-T03 | Agent tool bus | Redis Streams `bus:agent:commands` / `bus:agent:results`, typed `AgentMessage` (Pydantic, versioned, logged) (FR-ORC-05) |
| P6-T04 | Timeouts and fallbacks | Per-node timeouts, retries and degradations exactly as the table in `ARCHITECTURE.md §6.3` (FR-ORC-03) |
| P6-T05 | Directives | `WIDEN_WINDOW`, `EXCLUDE_ACCOUNT`, `FORCE_REATTRIBUTION` re-enter `attribute` (FR-ORC-04); overlap merge ≥ 50 % (FR-ORC-07) |
| P6-T06 | Assess | Case confidence formula; completeness; clause mapper from `config/regulatory_clauses.yaml`; rationale text rendered from templates only (never free LLM text) |
| P6-T07 | Narrator | LLM structured output → Pydantic validation → retries ≤ 2 → `TemplateNarrator`; set `narrative_mode` |
| P6-T08 | Validator | Schema validation; every sentence in `executive_summary` and `timeline[].description` has ≥ 1 resolvable `evidence_id`; numeric consistency (volumes sum, timestamps in window) (FR-DOS-02) |
| P6-T09 | Evidence capture | `TRADE_SLICE, L2_SLICE, L3_SLICE, SOCIAL_SLICE, ANOMALY_EVENT, GRAPH_EXPORT, CHART_IMAGE, LLM_TRACE, CONFIG_SNAPSHOT` with deterministic serialization; `evidence_id = EV-{TYPE}-{sha256[:12]}` |
| P6-T10 | Ledger | Append-only table, DB triggers blocking `UPDATE/DELETE/TRUNCATE`, advisory-lock single writer, `entry_hash = SHA256(prev ‖ evidence_sha256 ‖ ts ‖ type ‖ actor)`; daily Merkle anchor to object-lock bucket (NFR-SEC-01, 02) |
| P6-T11 | Merkle + signing | RFC 6962 domain separation (`0x00` leaf, `0x01` node); JCS canonicalization (RFC 8785); Ed25519 over SHA-256 digest; `Signer` interface with `FileEd25519Signer` and a `VaultTransitSigner` stub; key registry never deletes keys (FR-DOS-08, 10) |
| P6-T12 | PDF + bundle | Jinja2 + WeasyPrint, ≥ 6 sections, QR to verify URL, manifest hash embedded; `bundle.zip` layout per `ARCHITECTURE.md §10.5` (FR-DOS-05) |
| P6-T13 | Verifier | Six checks: schema, evidence hashes, Merkle root, ledger chain + anchor inclusion, JCS digest recompute, Ed25519 signature (+ review present when published). CLI `vigil-verify`, importable by API (FR-DOS-09) |
| P6-T14 | Versioning + review | Immutable versions with `supersedes`; review (`APPROVED/REJECTED/REWORK`) records identity, timestamp, comment; approval triggers final re-sign (FR-DOS-06, 07); `PUBLISHED` blocked with HTTP 409 without compliance approval |
| P6-T15 | Reveal flow | `reveal` service function: pepper-registry re-identification, audit + ledger entry (G-3) |

**Acceptance criteria**

| ID | Criterion | Verify |
|---|---|---|
| AC-ORC-01 | `pump_dump_ring_01` traverses `OPENED → … → PENDING_REVIEW` automatically in < 5 min | `scripts/gates/phase_6.sh orc01` |
| AC-ORC-02 | Killing the orchestrator mid-case and restarting resumes with **no duplicate ledger entries** | `scripts/chaos_test.sh orchestrator` then `pytest tests/integration/test_resume_no_dupes.py` |
| AC-ORC-03 | LLM blocked ⇒ dossier produced with `narrative_mode="TEMPLATE"` | `pytest tests/integration/test_template_mode.py` |
| AC-DOS-01 | Dossier validates against `forensic_dossier.schema.json`; all claims cited | `pytest tests/integration/test_dossier_schema.py` |
| AC-DOS-02 | `POST /verify` → `valid:true`; flipping any single byte of any evidence file → `valid:false` with named failure | `pytest tests/integration/test_tamper.py` |
| AC-DOS-03 | SQL `UPDATE/DELETE` on `evidence_ledger` raises | `pytest tests/integration/test_ledger_immutable.py` |
| AC-DOS-04 | `vigil-verify bundle.zip --pubkey keys/dev_ed25519.pub` exits 0 on valid, non-zero on tampered | `make verify BUNDLE=...` |
| AC-DOS-05 | PDF has ≥ 6 sections, manifest hash, QR code, opens cleanly | `pytest tests/integration/test_pdf.py` |
| AC-DOS-06 | Cannot reach `PUBLISHED` without compliance approval (409) | `pytest tests/integration/test_publish_gate.py` |
| P6-G1 | Same inputs + config hash ⇒ identical dossier digest (reproducibility, NFR-INT-02) when `narrative_mode=TEMPLATE` | `pytest tests/integration/test_repro_digest.py` |

**Exit gate:** all checked. A signed sample bundle is saved at `reports/sample_bundle/` and verified by the CLI in the log.

**Handoff block:** final state diagram diff vs. the document (if any); key id used; sample dossier id; the narrative prompt version; anything the legal reviewer must look at.

---

### PHASE 7 — API & Investigator UI

**Objective.** Finish the serving plane (REST + WebSocket + RBAC) and deliver the complete investigator interface exactly as specified in `DESIGN.md`.

**Read first:** `ARCHITECTURE.md` §11 (API), §12 (security); **all of `DESIGN.md`**; FR-API-*, FR-UI-*.

**Prerequisites:** Phase 6 `COMPLETE`.

**Human inputs:** none required. Optional: brand name/logo override; OIDC details if the human wants real SSO now.

**Tasks — API**

| ID | Task | Detail |
|---|---|---|
| P7-T01 | Router split | Break `services/api/src/api/main.py` into routers: `health, auth, symbols, anomalies, social, cases, evidence, dossiers, verify, ledger, admin, sim, ws` |
| P7-T02 | AuthN/Z | JWT (dev HS256 via `/auth/dev-token`, disabled when `ENV=prod`); OIDC validation when configured; RBAC `investigator, compliance_officer, admin, auditor_readonly` via `config/rbac.yaml`; role-gated text redaction on `/social/signals` |
| P7-T03 | Errors, limits | RFC 7807 `problem+json`; cursor pagination; `ratelimit:{role}:{route}` in Redis; every mutating call audited/ledgered |
| P7-T04 | Endpoints | Complete the table in `ARCHITECTURE.md §11.1` including `directives`, `links/feedback`, `submit`, `review`, `reveal`, `ledger/verify`, `dossiers/*/bundle|pdf|verify`, `POST /verify` |
| P7-T05 | WebSocket | `/ws/v1/stream?topics=heatmap,anomalies,cases,hype:{ticker}`; Kafka consumer per instance + Redis `mrs:*` poll (1 s); 15 s heartbeat; resumable with `?since=` |
| P7-T06 | UI-supporting endpoints | The additions listed in `DESIGN.md §14` (case summary card, timeline merge, evidence preview) |

**Tasks — UI** (full specs in `DESIGN.md`)

| ID | Task | Detail |
|---|---|---|
| P7-T10 | Design foundation | Tokens, Tailwind config, fonts, theme switch (Lightbox / Deep bench / auto), density setting; **delete every ad-hoc `slate-*`/hex class** and replace with tokens (a lint rule enforces it) |
| P7-T11 | `src/lib/` | `api.ts` (typed client from OpenAPI), `time.ts` (UTC store, IST/ET display), `format.ts`, `copy.ts` (microcopy + plain-language explanations), `query.ts` |
| P7-T12 | Primitives | Button, Chip, Meter, Table (virtualized), Popover, Dialog, Drawer, Toaster, CopyHash, EvidenceTag, Skeleton, EmptyState, ErrorState, CommandPalette |
| P7-T13 | App shell | Rail, TopBar (connection status, clock, global search), CaseBar with stepper, role gating |
| P7-T14 | `/live` Watch floor | Ranked watch ladder (not tiles), alert feed, mini-tape, wall-display mode |
| P7-T15 | `/cases` | Filterable, URL-synced queue, saved views |
| P7-T16 | `/cases/[id]` workbench | The **Tape**, anomaly list, evidence drawer, agent activity stream, case summary |
| P7-T17 | `/cases/[id]/graph` | Cytoscape explorer: layout switcher, cycle highlight, cluster coloring, inferred (dashed UV) vs observed (solid), edge inspector, confirm/reject, table alternative for accessibility |
| P7-T18 | `/cases/[id]/timeline` | Unified chronology |
| P7-T19 | `/dossiers/[id]` | Serif document view, numbered citations, integrity panel (live verify), review panel, export, print stylesheet |
| P7-T20 | `/verify` | Drag-and-drop bundle verifier; client-side WebCrypto Ed25519 where supported, server fallback |
| P7-T21 | `/entities/[id]`, `/simulator`, `/admin/health`, `/login` | Per `DESIGN.md §9` |
| P7-T22 | Quality | Playwright e2e for both personas' full journeys; Axe in CI (0 serious/critical); Lighthouse budget; keyboard map; reduced-motion; visual snapshot baselines |

**Acceptance criteria**

| ID | Criterion | Verify |
|---|---|---|
| AC-UI-01 | All FR-UI-01..08 routes render without console errors; Playwright suite passes | `pnpm --dir frontend test:e2e` |
| AC-UI-02 | Graph explorer renders 500 nodes at ≥ 30 fps on a mid-range laptop profile | `pnpm --dir frontend test:perf-graph` |
| P7-G1 | Role matrix test: each endpoint × role returns the documented status | `pytest tests/integration/test_rbac_matrix.py` |
| P7-G2 | Axe: 0 serious/critical on every route, both themes | `pnpm --dir frontend test:a11y` |
| P7-G3 | Lighthouse: LCP / time-to-first-chart < 2.5 s (NFR-PERF-06), performance ≥ 90 | `pnpm --dir frontend lighthouse` |
| P7-G4 | Lint rule finds zero token bypasses (no raw hex, no `slate-*`) | `pnpm --dir frontend lint:tokens` |
| P7-G5 | Persona A and B end-to-end journeys (PRD v1 §2.1, §2.2) pass as one scripted Playwright story on `pump_dump_ring_01` | `pnpm --dir frontend test:e2e -g journeys` |
| P7-G6 | Interface copy never uses accusatory terms (lint on `copy.ts` and templates) | `pnpm --dir frontend lint:copy` |

**Exit gate:** all checked; screenshots of each route in both themes saved in `reports/ui/`.

**Handoff block:** route list with auth requirements; bundle sizes; a11y report; known UX debts.

---

### PHASE 8 — Hardening & Release (FINAL)

**Objective.** Prove the non-functional requirements, harden security, finish observability and documentation, rehearse the demo, and ship `v1.0.0`.

**Read first:** `ARCHITECTURE.md` §12–§15; NFR-*; every `reports/*.md` from earlier phases.

**Prerequisites:** Phase 7 `COMPLETE`.

**Human inputs**

| Item | Blocker? | Fallback |
|---|---|---|
| Hardware spec for the load test (reference: 8 vCPU / 16 GB) | Soft | Run on available hardware and record the spec; results are reported as measured, not as pass, if lower |
| Production target decisions (KMS/Vault, OIDC, managed Kafka) | No | Documented as post-MVP in `docs/production-notes.md` |
| Demo audience / duration | No | 10-minute default script |

**Tasks**

| ID | Task | Detail |
|---|---|---|
| P8-T01 | Load test | `make load-test`: 5,000 market ev/s and 500 social msg/s for 15 min, p99 ingest < 200 ms (NFR-PERF-01, 02); commit the Grafana screenshot and raw numbers |
| P8-T02 | Latency budgets | Verify NFR-PERF-03/04/05 with histograms; case-open → draft p95 < 5 min |
| P8-T03 | Chaos | `make chaos`: kill a consumer, Neo4j, Redis for 60 s each; reconcile row counts (AC-NFR-02) |
| P8-T04 | Disaster recovery | Backup and restore drill for Timescale, Neo4j, MinIO; record RPO/RTO measured |
| P8-T05 | Security pass | OWASP ASVS L2 checklist in `docs/security/asvs.md`; `pip-audit`, `pnpm audit`, `trivy` image scans; `gitleaks`; confirm TLS notes, headers (CSP, HSTS in prod), CORS allow-list, rate limits, dev-token disabled in prod |
| P8-T06 | Privacy pass | Retention job proof (G-5), pseudonymization sweep, reveal audit test, log redaction test |
| P8-T07 | Reproducibility pass | NFR-INT-02: run the demo twice, same seed, diff anomaly events and TEMPLATE-mode dossier digest |
| P8-T08 | Observability | Final Grafana dashboards, Prometheus alert rules (consumer lag, DLQ rate, SIGNER_DOWN, ledger verify failure), OpenTelemetry trace sample from tick to dossier |
| P8-T09 | Coverage and typing | ≥ 80 % on agents/detectors (AC-NFR-04), `mypy --strict` for all of `libs` and `services` |
| P8-T10 | Docs | Final `README.md`, `docs/runbook.md` (start, stop, recover, rotate keys), `docs/demo-script.md`, `docs/production-notes.md`, `docs/threat-model.md`, `CHANGELOG.md` |
| P8-T11 | Smoke and demo | `make smoke` < 10 min (AC-NFR-03); full demo rehearsal following `docs/demo-script.md` with the Playwright journeys recorded |
| P8-T12 | Release | Update `CHANGELOG.md`, bump versions, SBOM (`syft` or `uv export`), tag `v1.0.0`, create release notes, finalize `PHASE_STATE.md` as `PROJECT COMPLETE` |

**Acceptance criteria**

| ID | Criterion | Verify |
|---|---|---|
| AC-NFR-01 | Load test sustains NFR-PERF-02 for 15 min with p99 < 200 ms | `make load-test` |
| AC-NFR-02 | Chaos: no event loss after 60 s outage of consumer / Neo4j / Redis | `make chaos` |
| AC-NFR-03 | `make smoke` completes < 10 min, exit 0 | `time make smoke` |
| AC-NFR-04 | `mypy --strict`, `ruff`, `pytest` ≥ 80 % on detectors in CI | CI URL |
| P8-G1 | Zero high/critical findings from pip-audit, pnpm audit, trivy (or each has a documented, dated exception) | scan outputs in `reports/security/` |
| P8-G2 | All previous gates re-run green on a clean clone: `for n in 1..7; make gate PHASE=$n` | pasted table |
| P8-G3 | Release artifacts exist: tag, changelog, SBOM, sample verified bundle, demo recording notes | checklist in `PHASE_STATE.md` |

**Exit gate:** every box above; `PHASE_STATE.md` shows `PROJECT COMPLETE`. The agent then stops. There is no phase 9.

**Handoff block (final):** release notes; list of accepted deviations; post-MVP backlog (vendor adapters, KMS/HSM signer, Neo4j cluster, multi-region); open legal-review items for counsel.

---

## 6. Requirement traceability (v1 IDs → phase)

| Requirement group | Phase |
|---|---|
| FR-MKT-01..08 | 2 |
| FR-QTA-01..08 | 2 |
| FR-SOC-01..08 | 3 |
| FR-ALN-01..05 | 4 |
| FR-GRA-01..09 | 5 |
| FR-ORC-01..07 | 6 |
| FR-DOS-01..10 | 6 |
| FR-API-01..03 | 7 |
| FR-UI-01..08 | 7 |
| NFR-PERF-01..06 | 2 (instrumentation) and 8 (proof) |
| NFR-HA-01..05 | 2 (shedding), 5 (graph buffer), 8 (chaos) |
| NFR-SEC-01..06, NFR-INT-01..02 | 6 and 8 |
| G-1..G-5 | 3 (G-3, G-5), 5 (G-2), 6 (G-1, G-4), 7 (UI display), 8 (audit) |
| G-6 (new) | 1 (policy), 2 (overlay), 6 (cover page), 7 (UI chip) |

---

## 7. Decision log (seed; the agent appends)

| # | Decision | Reason | Phase |
|---|---|---|---|
| D-1 | Keep v1 requirement IDs | Existing code and tests reference them | 0 |
| D-2 | Datasets come from one human-provided GitHub repo, pinned by commit SHA, hash-verified | Reproducibility; no hidden downloads | 1 |
| D-3 | CI never depends on external datasets | Keeps CI deterministic and free of secrets | 1 |
| D-4 | Add guardrail G-6 (synthetic labelling) | Public market data has no identities; overlay must never masquerade as real | 0 |
| D-5 | Real LangGraph replaces the Kafka-only `CaseOrchestrator` | PRD FR-ORC-01/02 require LangGraph checkpointing; `langgraph` was declared but unused | 6 |
| D-6 | UI follows `DESIGN.md` "Evidence Workbench"; tokens only | Existing components bypass tokens | 7 |

---

## 8. Definition of Done (project)

All eight phase gates are green on a clean clone; `make smoke` passes; a signed dossier from `pump_dump_ring_01` verifies offline with `vigil-verify`; both personas' journeys pass end-to-end in the browser; no accusatory copy; every synthetic-data case is labelled; `v1.0.0` is tagged; `PHASE_STATE.md` says `PROJECT COMPLETE`.
