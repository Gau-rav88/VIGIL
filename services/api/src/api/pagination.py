from __future__ import annotations

import base64
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


def encode_cursor(val: Any) -> str:
    s = str(val)
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        return base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    except Exception:
        return None


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    total: int | None = None
