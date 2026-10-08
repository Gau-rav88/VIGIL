import hashlib
from typing import Any


def compute_merkle_root(evidence_items: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """
    Compute RFC 6962-style domain separated Merkle tree.
    Leaves ordered by evidence_id ascending.
    Leaf hash = SHA256(0x00 || sha256_bytes_of_evidence).
    Parent hash = SHA256(0x01 || left || right).
    """
    if not evidence_items:
        empty_root = hashlib.sha256(b"").hexdigest()
        return empty_root, []

    # Sort items by evidence_id
    sorted_items = sorted(evidence_items, key=lambda x: str(x["evidence_id"]))

    leaves: list[bytes] = []
    for item in sorted_items:
        evidence_sha256 = bytes.fromhex(item["sha256"])
        leaf_hash = hashlib.sha256(b"\x00" + evidence_sha256).digest()
        leaves.append(leaf_hash)

    current_level = leaves
    proofs: list[dict[str, Any]] = [
        {"evidence_id": item["evidence_id"], "leaf_hash": leaves[idx].hex(), "path": []}
        for idx, item in enumerate(sorted_items)
    ]

    while len(current_level) > 1:
        next_level: list[bytes] = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            if i + 1 < len(current_level):
                right = current_level[i + 1]
                parent = hashlib.sha256(b"\x01" + left + right).digest()
            else:
                parent = left  # Promote odd node unchanged
            next_level.append(parent)
        current_level = next_level

    root_hex = current_level[0].hex()
    return root_hex, proofs
