# VIGIL Datasets Layer

This directory manages dataset ingestion for market microstructure and OSINT/social intelligence streams.

## Principles & Guardrails
- **Reproducibility:** Datasets are tracked via `datasets/manifest.yaml` and verified with cryptographic SHA-256 digests.
- **Honest Labelling (Guardrail G-6):** Any dataset containing simulated data or synthetic account identifiers must declare `is_synthetic: true`.
- **Offline / CI Decoupling:** Unit and contract tests NEVER depend on external network downloads; CI uses small fixtures committed in `tests/fixtures/`.
- **Automated Fetch:** Use `make datasets` or `./scripts/fetch_datasets.sh` to populate `datasets/data/` from the remote repository.

## Directory Structure
- `manifest.yaml` — Master inventory of datasets with expected SHA-256 checksums and target JSON schemas.
- `data/` — Local directory containing downloaded datasets (ignored by git).
- `data/.fetch_receipt.json` — Audit receipt recording origin repository, commit SHA, and verified hashes.
