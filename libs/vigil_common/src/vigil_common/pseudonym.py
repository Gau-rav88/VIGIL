import base64
import hashlib
import hmac


def pseudonymize(value: str, pepper: str, prefix: str = "") -> str:
    """
    Produce base64url-encoded truncated HMAC-SHA-256 pseudonym.
    Complies with schema pattern: ^[A-Za-z0-9_-]{22,64}$
    """
    data = f"{prefix}|{value}".encode("utf-8") if prefix else value.encode("utf-8")
    mac = hmac.new(pepper.encode("utf-8"), data, hashlib.sha256).digest()
    # 16 bytes base64url yields 22 chars without padding
    return base64.urlsafe_b64encode(mac[:16]).decode("ascii").rstrip("=")
