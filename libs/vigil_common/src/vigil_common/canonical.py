from typing import Any

import rfc8785


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonicalize a Python dictionary/list to byte-stable UTF-8 bytes per RFC 8785 (JCS)."""
    return rfc8785.dumps(obj)


def canonical_json_str(obj: Any) -> str:
    """Canonicalize to string per RFC 8785 (JCS)."""
    return canonical_json_bytes(obj).decode("utf-8")
