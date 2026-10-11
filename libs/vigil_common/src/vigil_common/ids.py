import os
import time
import uuid

VIGIL_NAMESPACE = uuid.UUID("4c81f3e0-6a5d-4f1e-9a5c-1b7f3d2e8a90")


def to_event_uuid(source: str, event_id: str | uuid.UUID) -> uuid.UUID:
    """Return the UUID unchanged if event_id is already a valid UUID;
    otherwise return uuid5(VIGIL_NAMESPACE, f"{source}|{event_id}")."""
    if isinstance(event_id, uuid.UUID):
        return event_id
    if not isinstance(event_id, str):
        event_id = str(event_id)
    try:
        return uuid.UUID(event_id)
    except (ValueError, AttributeError):
        return uuid.uuid5(VIGIL_NAMESPACE, f"{source}|{event_id}")


def uuid7() -> str:
    """Generate RFC 9562 UUIDv7 (time-ordered 128-bit UUID)."""
    # 48-bit timestamp in ms
    timestamp_ms = int(time.time() * 1000)
    rand_bytes = os.urandom(10)

    # 48 bits timestamp
    ts_bytes = timestamp_ms.to_bytes(6, byteorder="big")

    # Combine: 6 bytes ts + 2 bytes (ver 7 + rand) + 8 bytes (var 2 + rand)
    b0 = ts_bytes[0]
    b1 = ts_bytes[1]
    b2 = ts_bytes[2]
    b3 = ts_bytes[3]
    b4 = ts_bytes[4]
    b5 = ts_bytes[5]

    b6 = 0x70 | (rand_bytes[0] & 0x0F)
    b7 = rand_bytes[1]

    b8 = 0x80 | (rand_bytes[2] & 0x3F)
    b9 = rand_bytes[3]
    b10_15 = rand_bytes[4:10]

    raw = bytes([b0, b1, b2, b3, b4, b5, b6, b7, b8, b9]) + b10_15
    return str(uuid.UUID(bytes=raw))


def make_evidence_id(evidence_type: str, sha256_hex: str) -> str:
    """Format evidence identifier per ARCHITECTURE.md §9.1: EV-{TYPE}-{first 12 hex}."""
    return f"EV-{evidence_type.upper()}-{sha256_hex[:12]}"
