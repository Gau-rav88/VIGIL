#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
KEYS_DIR="${ROOT_DIR}/keys"

mkdir -p "${KEYS_DIR}"

PRIV_KEY="${KEYS_DIR}/dev_ed25519.pem"
PUB_KEY="${KEYS_DIR}/dev_ed25519.pub"

if [ -f "${PRIV_KEY}" ] && [ -f "${PUB_KEY}" ]; then
    echo "[gen_dev_keys] Dev keys already exist at ${KEYS_DIR}."
    exit 0
fi

echo "[gen_dev_keys] Generating Ed25519 dev key pair..."
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

priv = ed25519.Ed25519PrivateKey.generate()
priv_bytes = priv.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
pub = priv.public_key()
pub_bytes = pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

with open('${PRIV_KEY}', 'wb') as f:
    f.write(priv_bytes)

with open('${PUB_KEY}', 'wb') as f:
    f.write(pub_bytes)
"

chmod 600 "${PRIV_KEY}"
chmod 644 "${PUB_KEY}"
echo "[gen_dev_keys] Key generation successful: ${PRIV_KEY}, ${PUB_KEY}"
