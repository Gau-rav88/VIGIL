import base64
from pathlib import Path
from typing import Protocol
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


class Signer(Protocol):
    key_id: str

    def sign(self, digest: bytes) -> bytes:
        ...

    def public_key_pem(self) -> str:
        ...


class FileEd25519Signer:
    def __init__(self, key_path: str, key_id: str = "dev-2026-01") -> None:
        self.key_id = key_id
        self._key_path = Path(key_path)
        with open(self._key_path, "rb") as f:
            self._priv_key = serialization.load_pem_private_key(f.read(), password=None)
        if not isinstance(self._priv_key, ed25519.Ed25519PrivateKey):
            raise ValueError(f"Key in {key_path} is not an Ed25519 private key")

    def sign(self, digest: bytes) -> bytes:
        return self._priv_key.sign(digest)

    def public_key_pem(self) -> str:
        pub = self._priv_key.public_key()
        return pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")


def verify_ed25519(public_key_pem: str, digest: bytes, signature_b64: str) -> bool:
    try:
        pub_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        if not isinstance(pub_key, ed25519.Ed25519PublicKey):
            return False
        sig_bytes = base64.b64decode(signature_b64)
        pub_key.verify(sig_bytes, digest)
        return True
    except Exception:
        return False
