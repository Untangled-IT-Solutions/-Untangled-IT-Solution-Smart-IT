from __future__ import annotations
from typing import Any, Optional
from app.services.backend_api_client import BackendAPIClient


class Session:
    def __init__(self, api: BackendAPIClient) -> None:
        self.api = api
        self.user: Optional[dict[str, Any]] = None

    @property
    def role(self) -> str:
        return str((self.user or {}).get("role") or "Staff")

    @property
    def display_name(self) -> str:
        u = self.user or {}
        return str(u.get("full_name") or u.get("name") or u.get("username") or u.get("email") or "")

    @property
    def username(self) -> str:
        u = self.user or {}
        return str(u.get("username") or u.get("email") or "")

    def login(self, username: str, password: str) -> dict[str, Any]:
        data = self.api.login(username, password)
        user = data.get("user") or data.get("account") or data
        if not isinstance(user, dict):
            user = {"username": username}
        self.user = user
        return user

    def clear(self) -> None:
        try:
            self.api.logout()
        except Exception:
            pass
        self.user = None
        if hasattr(self.api, "token"):
            self.api.token = None
        if hasattr(self.api, "clear_cache"):
            self.api.clear_cache()
