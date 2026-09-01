"""
HTTP client used by the Windows desktop application.

Priority:
1. API_BASE_URL from .env
2. Local development server (localhost:10000)
3. Render production server
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter


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
            os.environ.setdefault(
                key.strip(),
                value.strip().strip('"').strip("'")
            )
    except OSError:
        pass


_load_env_file(_app_dir() / ".env")
_load_env_file(Path.cwd() / ".env")


class BackendAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        code: str = "",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class BackendAPIClient:
    """HTTP client for Untangled Nexus."""

    LOCAL_URL = "http://localhost:10000"
    RENDER_URL = "https://untangled-nexus-api.onrender.com"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 60.0,  # Render free tier cold starts
    ):
        env_url = os.getenv("API_BASE_URL", "").strip()

        self.base_url = (
            base_url
            or env_url
            or self.LOCAL_URL
        ).rstrip("/")

        self.timeout = timeout
        self.token: Optional[str] = None
        # Reuse TCP/TLS connections instead of opening a new connection for
        # every click. This is especially noticeable on the remote Render API.
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=0)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self.session: Optional[dict[str, Any]] = None

        print(f"🌐 Backend API: {self.base_url}")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Perform an HTTP request using a pooled session.

        The client remains synchronous by design; views are responsible for
        running blocking requests in background workers. Connection pooling
        here removes avoidable TCP/TLS setup time between requests.
        """
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        url = self._url(path)
        method = method.upper()
        print(f"➡️ {method} {url}")

        try:
            if method in {"GET", "HEAD", "DELETE"}:
                response = self._session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=(10, self.timeout),
                )
            else:
                headers["Content-Type"] = "application/json"
                response = self._session.request(
                    method,
                    url,
                    json=payload,
                    headers=headers,
                    timeout=(10, self.timeout),
                )

            try:
                data = response.json() if response.content else {}
            except ValueError:
                data = {}

            if not response.ok:
                message = (
                    data.get("error")
                    or data.get("message")
                    or f"Backend returned HTTP {response.status_code}"
                )
                raise BackendAPIError(message, response.status_code)

        except requests.exceptions.Timeout as exc:
            raise BackendAPIError("Backend request timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            # Keep the existing development convenience: if localhost is not
            # running, transparently try the configured production API once.
            if self.base_url == self.LOCAL_URL:
                print("⚠️ Local backend unavailable. Switching to Render...")
                self.base_url = self.RENDER_URL
                return self.request(method, path, payload)
            raise BackendAPIError("Cannot connect to backend server.") from exc
        except BackendAPIError:
            raise
        except requests.exceptions.RequestException as exc:
            raise BackendAPIError(str(exc)) from exc
        except Exception as exc:
            raise BackendAPIError(str(exc)) from exc

        if not isinstance(data, dict):
            raise BackendAPIError("Invalid backend response.")

        if data.get("success") is False:
            raise BackendAPIError(
                str(data.get("error") or data.get("message") or "Request failed.")
            )

        return data

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def login(self, username: str, password: str):
        data = self.request(
            "POST",
            "/api/auth/login",
            {
                "username": username,
                "password": password,
            },
        )

        self.token = data.get("token")
        self.session = data
        return data

    def me(self):
        return self.request("GET", "/api/auth/me")

    def logout(self):
        try:
            if self.token:
                self.request("POST", "/api/auth/logout")
        finally:
            self.token = None
            self.session = None

    # ------------------------------------------------------------------
    # Attendance - FIXED with proper HTTP methods
    # ------------------------------------------------------------------

    def attendance_status(self):
        """Get current attendance status (GET)"""
        return self.request("GET", "/api/attendance/status")

    def clock_in(self, employee_id: int = None):
        """Clock in (POST)"""
        payload = {"employee_id": employee_id} if employee_id else {}
        return self.request("POST", "/api/attendance/clock-in", payload)

    def clock_out(self, employee_id: int = None):
        """Clock out (POST)"""
        payload = {"employee_id": employee_id} if employee_id else {}
        return self.request("POST", "/api/attendance/clock-out", payload)

    def break_start(self, employee_id: int = None):
        """Start break (POST)"""
        payload = {"employee_id": employee_id} if employee_id else {}
        return self.request("POST", "/api/attendance/break/start", payload)

    def break_end(self, employee_id: int = None):
        """End break (POST)"""
        payload = {"employee_id": employee_id} if employee_id else {}
        return self.request("POST", "/api/attendance/break/end", payload)

    def attendance(self, path: str, payload=None):
        """
        Legacy attendance method - maintains compatibility with existing code.
        Automatically uses POST for actions and GET for status.
        """
        action_endpoints = ["clock-in", "clock-out", "break/start", "break/end"]
        is_action = any(endpoint in path for endpoint in action_endpoints)
        
        if is_action:
            # Actions need POST even without payload
            return self.request("POST", path, payload or {})
        
        # Status endpoints use GET
        return self.request("GET", path, payload)

    # ------------------------------------------------------------------
    # Quotes
    # ------------------------------------------------------------------

    def get_quotes(self):
        """Get all quotes (GET)"""
        return self.request("GET", "/api/quotes")

    def create_quote(self, data: dict):
        """Create a new quote (POST)"""
        return self.request("POST", "/api/quotes", data)

    def track_quote(self, ref: str, email: str):
        """Track a quote by reference and email (GET)"""
        return self.request("GET", "/api/quotes/track?" + urlencode({"ref": ref, "email": email}))

    def assign_quote(self, reference: str, employee_id: str):
        """Assign a quote to an employee (PUT)"""
        return self.request(
            "PUT",
            f"/api/admin/quotes/{reference}/assignment",
            {"employee_id": employee_id}
        )

    def request_director_review(self, reference: str, payload: dict = None):
        """Employee sends quote to Director for availability check (POST)."""
        return self.request(
            "POST",
            f"/api/admin/quotes/{reference}/director-review/request",
            payload or {},
        )

    def submit_director_review(self, reference: str, payload: dict):
        """Director submits item availability + general reply (PUT)."""
        return self.request(
            "PUT",
            f"/api/admin/quotes/{reference}/director-review",
            payload,
        )

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def get_orders(self):
        """Get all orders (GET)"""
        return self.request("GET", "/api/orders")

    def create_order(self, data: dict):
        """Create a new order (POST)"""
        return self.request("POST", "/api/orders", data)

    def track_order(self, ref: str, email: str):
        """Track an order by reference and email (GET)"""
        return self.request("GET", "/api/orders/track?" + urlencode({"ref": ref, "email": email}))

    # ------------------------------------------------------------------
    # Employees
    # ------------------------------------------------------------------

    def get_employees(self):
        """Get all employees (GET)"""
        return self.request("GET", "/api/employees")

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dashboard_summary(self):
        """Get dashboard summary data (GET)"""
        return self.request("GET", "/api/dashboard/summary")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self):
        return self.request("GET", "/api/health")