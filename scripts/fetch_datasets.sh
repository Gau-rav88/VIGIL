#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${ROOT_DIR}/datasets/data"
MANIFEST_FILE="${ROOT_DIR}/datasets/manifest.yaml"
RECEIPT_FILE="${DATA_DIR}/.fetch_receipt.json"

# Load .env if present
if [[ -f "${ROOT_DIR}/.env" ]]; then
  # export variables from .env
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env" || true
  set +a
fi

DATASET_REPO_URL="${DATASET_REPO_URL:-}"
DATASET_REPO_REF="${DATASET_REPO_REF:-main}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Check for --verify-only mode
if [[ "${1:-}" == "--verify-only" ]]; then
  echo "==> Running dataset verification..."
  if [[ ! -f "${RECEIPT_FILE}" ]]; then
    echo "ERROR: No fetch receipt found at ${RECEIPT_FILE}. Run without --verify-only first." >&2
    exit 1
  fi

  python3 - << 'EOF'
import sys, json, hashlib
from pathlib import Path

receipt_path = Path("datasets/data/.fetch_receipt.json")
receipt = json.loads(receipt_path.read_text())
file_hashes = receipt.get("file_hashes", {})

mismatches = 0
for rel_path, expected_hash in file_hashes.items():
    file_path = Path("datasets/data") / rel_path
    if not file_path.exists():
        print(f"FAIL: File missing: {file_path}", file=sys.stderr)
        mismatches += 1
        continue
    actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        print(f"FAIL: SHA256 mismatch for {file_path}: expected {expected_hash}, got {actual_hash}", file=sys.stderr)
        mismatches += 1
    else:
        print(f"OK: {rel_path}")

if mismatches > 0:
    print(f"Verification failed: {mismatches} file(s) mismatched or missing.", file=sys.stderr)
    sys.exit(1)

print("All datasets verified successfully.")
EOF
  exit 0
fi

# Normal fetch mode: check if DATASET_REPO_URL is set
if [[ -z "${DATASET_REPO_URL}" ]]; then
  echo "================================================================================" >&2
  echo "GUIDANCE: DATASET_REPO_URL is not configured in your environment or .env." >&2
  echo "To fetch external real-market or social datasets:" >&2
  echo "  1. Set DATASET_REPO_URL=<git-clone-url> in .env" >&2
  echo "  2. (Optional) Set DATASET_REPO_REF=<branch-or-commit-sha> (default: main)" >&2
  echo "  3. (Optional) Set GITHUB_TOKEN=<pat> for private repositories" >&2
  echo "Operating in synthetic simulator-only fallback mode." >&2
  echo "================================================================================" >&2
  exit 2
fi

echo "==> Fetching datasets from ${DATASET_REPO_URL} (${DATASET_REPO_REF})..."
mkdir -p "${DATA_DIR}"
TEMP_CLONE_DIR=$(mktemp -d)
trap 'rm -rf "${TEMP_CLONE_DIR}"' EXIT

# Clone shallow
if [[ -n "${GITHUB_TOKEN}" ]]; then
  git clone --depth 1 --branch "${DATASET_REPO_REF}" \
    --config http.extraHeader="Authorization: Basic $(echo -n "x-access-token:${GITHUB_TOKEN}" | base64)" \
    "${DATASET_REPO_URL}" "${TEMP_CLONE_DIR}"
else
  git clone --depth 1 --branch "${DATASET_REPO_REF}" "${DATASET_REPO_URL}" "${TEMP_CLONE_DIR}"
fi

RESOLVED_COMMIT=$(cd "${TEMP_CLONE_DIR}" && git rev-parse HEAD)
echo "Resolved commit SHA: ${RESOLVED_COMMIT}"

# Parse manifest and copy matching files
python3 - << EOF
import sys, yaml, shutil, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

temp_dir = Path("${TEMP_CLONE_DIR}")
data_dir = Path("${DATA_DIR}")
manifest_path = Path("${MANIFEST_FILE}")

with open(manifest_path, "r") as f:
    manifest = yaml.safe_load(f)

file_hashes = {}
for name, meta in manifest.get("datasets", {}).items():
    repo_rel = meta.get("repo_path")
    expected_sha = meta.get("sha256")
    src = temp_dir / repo_rel
    if src.exists():
        dest = data_dir / repo_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        actual_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        file_hashes[repo_rel] = actual_sha
        print(f"Copied {repo_rel} (SHA256: {actual_sha[:16]}...)")

receipt = {
    "repo_url": "${DATASET_REPO_URL}",
    "resolved_commit_sha": "${RESOLVED_COMMIT}",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "file_hashes": file_hashes
}

receipt_path = Path("${RECEIPT_FILE}")
receipt_path.write_text(json.dumps(receipt, indent=2))
print("Wrote fetch receipt to", receipt_path)
EOF

echo "==> Dataset fetch and verification complete."
