"""Process-wide TTL cache for view data – UI thread never waits on network for cached hits."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

_lock = threading.RLock()
_store: dict[str, tuple[float, Any]] = {}

# Sensible defaults (seconds)
DEFAULT_TTL = 45.0
TTL_BY_PREFIX = {
    "dashboard": 20.0,
    "people": 60.0,
    "notifications": 15.0,
    "tasks": 30.0,
    "attendance": 15.0,
    "calendar": 60.0,
    "approvals": 30.0,
    "projects": 60.0,
    "quotes": 30.0,
    "orders": 30.0,
    "reports": 90.0,
}


def _ttl_for(key: str) -> float:
    prefix = key.split(":", 1)[0].lower()
    return TTL_BY_PREFIX.get(prefix, DEFAULT_TTL)


def get(key: str) -> Optional[Any]:
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        expires, value = entry
        if time.monotonic() > expires:
            _store.pop(key, None)
            return None
        return value


def set(key: str, value: Any, ttl: Optional[float] = None) -> None:
    life = ttl if ttl is not None else _ttl_for(key)
    with _lock:
        _store[key] = (time.monotonic() + max(1.0, life), value)


def invalidate(prefix: str = "") -> None:
    """Drop one key or all keys starting with prefix."""
    with _lock:
        if not prefix:
            _store.clear()
            return
        dead = [k for k in _store if k == prefix or k.startswith(prefix)]
        for k in dead:
            _store.pop(k, None)


def get_or_fetch(key: str, fetcher: Callable[[], Any], ttl: Optional[float] = None) -> Any:
    """Return cached value or call fetcher (runs on caller thread – use from workers only)."""
    cached = get(key)
    if cached is not None:
        return cached
    value = fetcher()
    set(key, value, ttl=ttl)
    return value
