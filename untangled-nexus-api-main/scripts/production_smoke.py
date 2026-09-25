from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base_url = os.environ.get("NEXUS_API_URL", "").rstrip("/")
if not base_url:
    raise SystemExit("NEXUS_API_URL is required")


def get(path: str, timeout: float = 15.0) -> tuple[dict, float]:
    started = time.perf_counter()
    headers = {"Accept": "application/json"}
    if path == "/api/metrics" and os.environ.get("METRICS_TOKEN"):
        headers["X-Metrics-Token"] = os.environ["METRICS_TOKEN"]
    request = Request(base_url + path, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload, (time.perf_counter() - started) * 1000


def status(path: str, timeout: float = 15.0) -> int:
    request = Request(base_url + path, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status
    except HTTPError as exc:
        return exc.code


failures = []
for endpoint in ("/api/health", "/api/ready", "/api/metrics"):
    try:
        payload, duration_ms = get(endpoint)
        print(f"{endpoint}: {duration_ms:.1f} ms")
        if not payload.get("success"):
            failures.append(f"{endpoint} returned unsuccessful status")
        if endpoint != "/api/metrics" and duration_ms > 2_000:
            failures.append(f"{endpoint} exceeded 2000 ms")
    except Exception as exc:
        failures.append(f"{endpoint} failed: {type(exc).__name__}")

protected_routes = (
    "/api/dashboard/summary",
    "/api/dashboard/director",
    "/api/dashboard/business-lead",
    "/api/dashboard/operations",
    "/api/notifications/unread-count",
    "/api/notifications/stream",
)
for endpoint in protected_routes:
    try:
        response_status = status(endpoint)
        print(f"{endpoint}: HTTP {response_status}")
        if response_status not in (401, 403):
            failures.append(
                f"{endpoint} expected authentication response, got HTTP {response_status}"
            )
    except Exception as exc:
        failures.append(f"{endpoint} route check failed: {type(exc).__name__}")

if failures:
    print("\n".join(failures), file=sys.stderr)
    raise SystemExit(1)
print("Nexus production smoke checks passed")
