from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

_started_at = time.time()
_totals = {"requests": 0, "errors": 0, "slow_requests": 0}
_routes: dict[str, dict[str, Any]] = defaultdict(
    lambda: {"requests": 0, "errors": 0, "duration_ms_total": 0.0, "duration_ms_max": 0.0}
)


def record_request(route: str, status: int, duration_ms: float, slow_ms: int) -> None:
    _totals["requests"] += 1
    if status >= 500:
        _totals["errors"] += 1
    if duration_ms >= slow_ms:
        _totals["slow_requests"] += 1
    row = _routes[route]
    row["requests"] += 1
    row["errors"] += int(status >= 500)
    row["duration_ms_total"] += duration_ms
    row["duration_ms_max"] = max(row["duration_ms_max"], duration_ms)


def metrics_snapshot() -> dict[str, Any]:
    routes = {}
    for name, row in _routes.items():
        count = row["requests"] or 1
        routes[name] = {
            "requests": row["requests"],
            "errors": row["errors"],
            "duration_ms_avg": round(row["duration_ms_total"] / count, 1),
            "duration_ms_max": round(row["duration_ms_max"], 1),
        }
    return {
        **_totals,
        "uptime_seconds": round(time.time() - _started_at, 1),
        "routes": routes,
    }
