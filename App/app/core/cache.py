from __future__ import annotations
import time
from typing import Any, Optional

_store: dict[str, tuple[float, Any]] = {}

def get(key: str) -> Optional[Any]:
    e = _store.get(key)
    if not e:
        return None
    if time.monotonic() > e[0]:
        _store.pop(key, None)
        return None
    return e[1]

def set(key: str, value: Any, ttl: float = 45.0) -> None:
    _store[key] = (time.monotonic() + ttl, value)

def invalidate(prefix: str = "") -> None:
    if not prefix:
        _store.clear()
        return
    for k in [k for k in _store if k.startswith(prefix)]:
        _store.pop(k, None)
