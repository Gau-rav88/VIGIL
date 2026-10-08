import time
from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def now_rfc3339() -> str:
    """Return ISO 8601 / RFC 3339 string with Z suffix."""
    return now_utc().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def time_ns() -> int:
    """Current monotonic wall time in nanoseconds."""
    return time.time_ns()


def to_rfc3339(dt: datetime) -> str:
    """Convert datetime to standard RFC 3339 UTC string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
