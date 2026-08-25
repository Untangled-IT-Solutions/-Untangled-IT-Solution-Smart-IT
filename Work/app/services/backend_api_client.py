"""HTTP client used by the Windows desktop EXE to talk to the Backend API.

The EXE never receives or stores MongoDB credentials. Authentication and
attendance operations are performed by the backend, which talks to MongoDB.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
    except OSError:
        pass


_load_env_file(_app_dir() / ".env")
_load_env_file(Path.cwd() / ".env")


class BackendAPIError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class BackendAPIClient:
    """Small dependency-free HTTP client for the desktop API."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 12.0):
        # ✅ HARDCODED FALLBACK - This will ALWAYS work
        FALLBACK_URL = "https://untangled-nexus-api.onrender.com"
        
        # Try: passed URL → env variable → hardcoded fallback
        env_url = os.getenv("API_BASE_URL", "")
        self.base_url = (base_url or env_url or FALLBACK_URL).strip().rstrip("/")
        self.timeout = timeout
        self.token: Optional[str] = None
        self.session: Optional[dict[str, Any]] = None

        # ✅ No more error - we ALWAYS have a URL

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(self._url(path), data=body, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
        except HTTPError as exc:
            try:
                raw = exc.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {}
            message = data.get("error") or data.get("message") or f"Backend returned HTTP {exc.code}."
            raise BackendAPIError(message, exc.code, str(data.get("code") or "")) from exc
        except URLError as exc:
            raise BackendAPIError(
                "Cannot connect to the backend server. Check your internet connection or contact support."
            ) from exc
        except TimeoutError as exc:
            raise BackendAPIError("The backend server took too long to respond.") from exc
        except Exception as exc:
            raise BackendAPIError(f"Backend communication failed: {exc}") from exc

        if not isinstance(data, dict):
            raise BackendAPIError("The backend returned an invalid response.")
        if data.get("success") is False:
            raise BackendAPIError(
                str(data.get("error") or "Backend request failed."),
                code=str(data.get("code") or ""),
            )
        return data

    def login(self, username: str, password: str) -> dict[str, Any]:
        data = self.request("POST", "/api/auth/login", {"username": username, "password": password})
        token = data.get("token")
        if not token:
            raise BackendAPIError("The backend did not return a login session token.")
        self.token = str(token)
        self.session = data
        return data

    def me(self) -> dict[str, Any]:
        return self.request("GET", "/api/auth/me")

    def logout(self) -> None:
        try:
            if self.token:
                self.request("POST", "/api/auth/logout")
        finally:
            self.token = None
            self.session = None

    def attendance(self, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self.request("POST" if payload is not None else "GET", path, payload)

    def health(self) -> dict[str, Any]:
        return self.request("GET", "/api/health")