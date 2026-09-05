"""
Production HTTP client for Untangled Nexus Backend API.

- Single source of truth for all data (MongoDB lives only on the server).
- Connection pooling, retries on transient errors, clean error surface.
- Lightweight in-memory cache for frequently accessed data (people, dashboard).
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("untangled.api")


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_env_file(_app_dir() / ".env")
_load_env_file(Path.cwd() / ".env")
# Also try parent of app/ (project root when running python main.py)
_load_env_file(Path(__file__).resolve().parents[2] / ".env")


class BackendAPIError(RuntimeError):
    """Raised for any non-success backend response or network failure."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        code: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class BackendAPIClient:
    """Thread-safe-ish HTTP client with pooling and simple caching."""

    LOCAL_URL = "http://localhost:10000"
    RENDER_URL = "https://untangled-nexus-api.onrender.com"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 45.0,
    ) -> None:
        # Explicit and predictable:
        #   production  → API_BASE_URL or Render (never localhost fallback)
        #   development → API_BASE_URL or localhost
        env_name = (os.getenv("ENVIRONMENT") or "production").strip().lower()
        env_url = (os.getenv("API_BASE_URL") or "").strip()
        is_dev = env_name in {"development", "dev", "local"}
        if base_url:
            chosen = base_url
        elif env_url:
            chosen = env_url
        elif is_dev:
            chosen = self.LOCAL_URL
        else:
            chosen = self.RENDER_URL
        self.base_url = chosen.rstrip("/")
        self.timeout = timeout
        self._allow_dev_fallback = is_dev
        self.token: Optional[str] = None
        self.session_data: Optional[dict[str, Any]] = None

        print(f"🌐 Backend API client → {self.base_url} (env={env_name})")
        logger.info("Backend API client → %s", self.base_url)

        self._session = requests.Session()
        # GET-only retries for transient gateway errors (Render cold starts).
        # POST/auth is retried manually in login() so the user sees a clear message.
        retry = Retry(
            total=3,
            backoff_factor=1.2,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry,
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        # Simple TTL caches (seconds)
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = {
            "employees": 90.0,
            "dashboard": 45.0,
            "me": 120.0,
        }

        logger.info("Backend API client → %s", self.base_url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "UntangledNexus-Desktop/1.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_cache(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if not entry:
            return None
        expires, value = entry
        if time.time() > expires:
            self._cache.pop(key, None)
            return None
        return value

    def _set_cache(self, key: str, value: Any) -> None:
        ttl = self._cache_ttl.get(key, 60.0)
        self._cache[key] = (time.time() + ttl, value)

    def clear_cache(self) -> None:
        self._cache.clear()

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
        *,
        use_cache: bool = False,
        cache_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request. Returns parsed JSON dict."""
        method = method.upper()
        cache_key = cache_key or path.strip("/").replace("/", "_")

        if use_cache and method == "GET":
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached

        headers = self._headers()
        url = self._url(path)

        try:
            if method in {"GET", "HEAD", "DELETE"}:
                resp = self._session.request(
                    method, url, headers=headers, timeout=(20, self.timeout)
                )
            else:
                headers["Content-Type"] = "application/json"
                resp = self._session.request(
                    method, url, json=payload or {}, headers=headers, timeout=(20, self.timeout)
                )

            try:
                data = resp.json() if resp.content else {}
            except ValueError:
                data = {}

            if not resp.ok:
                message = (
                    data.get("error")
                    or data.get("message")
                    or f"Backend returned HTTP {resp.status_code}"
                )
                raise BackendAPIError(str(message), resp.status_code)

            if use_cache and method == "GET":
                self._set_cache(cache_key, data)

            return data

        except requests.exceptions.Timeout as exc:
            raise BackendAPIError("Backend request timed out. Please try again.") from exc
        except requests.exceptions.ConnectionError as exc:
            # Development only: if local API is down, optionally try production.
            # Production builds never silently switch environments.
            if self._allow_dev_fallback and self.base_url == self.LOCAL_URL:
                logger.warning("Local backend unavailable – switching to Render (development only)")
                self.base_url = self.RENDER_URL
                return self.request(method, path, payload, use_cache=use_cache, cache_key=cache_key)
            raise BackendAPIError(
                "Cannot connect to the server. Check your internet connection."
            ) from exc
        except BackendAPIError:
            raise
        except requests.exceptions.RequestException as exc:
            raise BackendAPIError(f"Network error: {exc}") from exc

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate against the backend. Requires a real token + user payload.

        Retries a few times on 502/503 (Render free-tier cold start / Mongo wake-up).
        """
        if not username or not password:
            raise BackendAPIError("Username and password are required.", status_code=400)

        last_err: Optional[Exception] = None
        # Render free tier can take 30–60s to wake; give login several chances.
        for attempt in range(1, 5):
            try:
                data = self.request(
                    "POST",
                    "/api/auth/login",
                    {"username": username.strip(), "password": password},
                )
                token = data.get("token") or data.get("access_token")
                user = data.get("user") or data.get("account")
                if not token:
                    raise BackendAPIError(
                        "Login failed: server did not return an authentication token.",
                        status_code=401,
                    )
                if not user:
                    raise BackendAPIError(
                        "Login failed: server did not return user details.",
                        status_code=401,
                    )
                self.token = token
                self.session_data = data
                self.clear_cache()
                return data
            except BackendAPIError as exc:
                last_err = exc
                code = getattr(exc, "status_code", None)
                msg = str(exc).lower()
                transient = code in (502, 503, 504) or "503" in msg or "unavailable" in msg or "timed out" in msg
                if not transient or attempt >= 4:
                    if code in (502, 503, 504) or "503" in msg:
                        raise BackendAPIError(
                            "Server is waking up or the database is offline. "
                            "Wait 30–60 seconds and try logging in again.",
                            status_code=code or 503,
                        ) from exc
                    raise
                wait = attempt * 3
                print(f"⏳ Login attempt {attempt} failed ({exc}); retrying in {wait}s…")
                time.sleep(wait)
            except Exception as exc:
                last_err = exc
                if attempt >= 4:
                    break
                time.sleep(attempt * 3)
        raise BackendAPIError(
            f"Cannot reach the server after several tries. {last_err}",
            status_code=503,
        )

    def me(self) -> dict[str, Any]:
        return self.request("GET", "/api/auth/me", use_cache=True, cache_key="me")

    def logout(self) -> None:
        try:
            if self.token:
                self.request("POST", "/api/auth/logout")
        except BackendAPIError:
            pass
        finally:
            self.token = None
            self.session_data = None
            self.clear_cache()

    # ------------------------------------------------------------------
    # Attendance
    # ------------------------------------------------------------------

    def attendance_status(self) -> dict[str, Any]:
        return self.request("GET", "/api/attendance/status")

    def clock_in(self, employee_id: Optional[int] = None) -> dict[str, Any]:
        payload = {"employee_id": employee_id} if employee_id is not None else {}
        return self.request("POST", "/api/attendance/clock-in", payload)

    def clock_out(self, employee_id: Optional[int] = None) -> dict[str, Any]:
        payload = {"employee_id": employee_id} if employee_id is not None else {}
        return self.request("POST", "/api/attendance/clock-out", payload)

    def break_start(self, employee_id: Optional[int] = None) -> dict[str, Any]:
        payload = {"employee_id": employee_id} if employee_id is not None else {}
        return self.request("POST", "/api/attendance/break/start", payload)

    def break_end(self, employee_id: Optional[int] = None) -> dict[str, Any]:
        payload = {"employee_id": employee_id} if employee_id is not None else {}
        return self.request("POST", "/api/attendance/break/end", payload)

    # ------------------------------------------------------------------
    # People / Employees
    # ------------------------------------------------------------------

    def get_employees(self, force: bool = False) -> list[dict[str, Any]]:
        if not force:
            cached = self._get_cache("employees")
            if cached is not None:
                return cached.get("employees") or cached if isinstance(cached, dict) else cached

        # Prefer admin endpoint when authenticated
        try:
            if self.token:
                data = self.request("GET", "/api/admin/employees", use_cache=False)
                employees = data.get("employees") or []
                if employees:
                    self._set_cache("employees", {"employees": employees})
                    return employees
        except BackendAPIError:
            pass

        data = self.request("GET", "/api/employees", use_cache=True, cache_key="employees")
        return data.get("employees") or []

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dashboard_summary(self) -> dict[str, Any]:
        return self.request(
            "GET", "/api/dashboard/summary", use_cache=True, cache_key="dashboard"
        )

    # ------------------------------------------------------------------
    # Quotes & Orders
    # ------------------------------------------------------------------

    def get_quotes(self) -> dict[str, Any]:
        return self.request("GET", "/api/quotes")

    def create_quote(self, data: dict) -> dict[str, Any]:
        return self.request("POST", "/api/quotes", data)

    def track_quote(self, ref: str, email: str) -> dict[str, Any]:
        return self.request("GET", f"/api/quotes/track?ref={ref}&email={email}")

    def assign_quote(self, reference: str, employee_id: str) -> dict[str, Any]:
        return self.request(
            "POST", f"/api/quotes/{reference}/assign", {"employee_id": employee_id}
        )

    def update_quote_status(
        self, reference: str, status: str, extra: Optional[dict] = None
    ) -> dict[str, Any]:
        payload = {"status": status}
        if extra:
            payload.update(extra)
        return self.request("PATCH", f"/api/quotes/{reference}/status", payload)

    def get_orders(self) -> dict[str, Any]:
        return self.request("GET", "/api/orders")

    def create_order(self, data: dict) -> dict[str, Any]:
        return self.request("POST", "/api/orders", data)

    def assign_order(self, reference: str, employee_id: str) -> dict[str, Any]:
        return self.request(
            "POST", f"/api/orders/{reference}/assign", {"employee_id": employee_id}
        )

    def update_order_status(
        self, reference: str, status: str, extra: Optional[dict] = None
    ) -> dict[str, Any]:
        payload = {"status": status}
        if extra:
            payload.update(extra)
        return self.request("PATCH", f"/api/orders/{reference}/status", payload)

    def request_director_review(
        self, reference: str, payload: Optional[dict] = None
    ) -> dict[str, Any]:
        return self.request(
            "POST", f"/api/quotes/{reference}/director-review", payload or {}
        )

    def submit_director_review(self, reference: str, payload: dict) -> dict[str, Any]:
        return self.request(
            "POST", f"/api/quotes/{reference}/director-review/submit", payload
        )

    def get_director_review(self, reference: str) -> dict[str, Any]:
        return self.request("GET", f"/api/quotes/{reference}/director-review")

    # ------------------------------------------------------------------
    # Tasks / Work (backend endpoints – extend as your API grows)
    # ------------------------------------------------------------------

    def get_tasks(self, scope: str = "all") -> dict[str, Any]:
        return self.request("GET", f"/api/tasks?scope={scope}")

    def get_task(self, task_id: str | int) -> dict[str, Any]:
        return self.request("GET", f"/api/tasks/{task_id}")

    def create_task(self, data: dict) -> dict[str, Any]:
        return self.request("POST", "/api/tasks", data)

    def update_task(self, task_id: str | int, data: dict) -> dict[str, Any]:
        """Update task – try PATCH then PUT (some hosts block PATCH)."""
        try:
            return self.request("PATCH", f"/api/tasks/{task_id}", data)
        except BackendAPIError as exc:
            if getattr(exc, "status_code", None) in (405, 404):
                return self.request("PUT", f"/api/tasks/{task_id}", data)
            raise

    def task_action(self, task_id: str | int, action: str, note: str = "") -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/tasks/{task_id}/{action}",
            {"note": note or ""},
        )

    def get_workload(self) -> dict[str, Any]:
        return self.request("GET", "/api/tasks/workload")

    def get_decision_queue(self) -> dict[str, Any]:
        return self.request("GET", "/api/tasks/decision-queue")

    # ------------------------------------------------------------------
    # Admin – Users / Accounts (Backend only)
    # ------------------------------------------------------------------

    def list_users(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        q = "include_inactive=1" if include_inactive else "include_inactive=0"
        data = self.request("GET", f"/api/admin/users?{q}")
        return data.get("users") or data.get("items") or []

    def get_user(self, user_id: str | int) -> dict[str, Any]:
        data = self.request("GET", f"/api/admin/users/{user_id}")
        return data.get("user") or data

    def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.request("POST", "/api/admin/users", payload)
        return data.get("user") or data

    def update_user(self, user_id: str | int, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.request("PATCH", f"/api/admin/users/{user_id}", payload)
        return data.get("user") or data

    def delete_user(self, user_id: str | int) -> dict[str, Any]:
        return self.request("DELETE", f"/api/admin/users/{user_id}")

    def reset_user_password(self, user_id: str | int, password: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/admin/users/{user_id}/reset-password",
            {"password": password},
        )

    def list_admin_employees(self) -> list[dict[str, Any]]:
        data = self.request("GET", "/api/admin/employees")
        return data.get("employees") or data.get("items") or []

    def get_admin_employee(self, employee_id: str | int) -> dict[str, Any]:
        data = self.request("GET", f"/api/admin/employees/{employee_id}")
        return data.get("employee") or data

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        return self.request("GET", "/api/health")
