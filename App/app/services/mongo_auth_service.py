"""Backend API authentication and administration adapter.

The desktop application never connects directly to MongoDB.  Authentication,
employee lookup, user administration, and password operations are performed
by the Backend API.
"""
from __future__ import annotations

from typing import Any, Optional
import hashlib
import secrets

from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class MongoAuthService:
    def __init__(self, backend: BackendAPIClient):
        self._backend = backend
        self._current_session: Optional[dict[str, Any]] = None

    @staticmethod
    def hash_password(password: str) -> str:
        iterations = 310_000
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    @staticmethod
    def generate_secure_password(length: int = 14) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*"
        return "".join(secrets.choice(alphabet) for _ in range(max(12, length)))

    @staticmethod
    def generate_username(full_name: str) -> str:
        cleaned = "".join(c.lower() if c.isalnum() else " " for c in (full_name or "")).split()
        if not cleaned:
            return f"user_{secrets.token_hex(4)}@untangledits.co.za"
        return f"{cleaned[0]}.{cleaned[-1]}@untangledits.co.za"

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        try:
            data = self._backend.login(username, password)
        except BackendAPIError as exc:
            # Any auth failure from the backend is a credential / account problem
            # for the desktop user — surface the backend message cleanly.
            raise PermissionError(str(exc) or "Invalid username or password.") from exc
        user = data.get("user") or {}
        employee = data.get("employee") or {}
        self._current_session = {
            "token": data.get("token"),
            "login_at": data.get("expires_at"),
            "last_activity_at": data.get("expires_at"),
            "status": "active",
        }
        return {"user": user, "employee": employee, "session": self._current_session, "token": data.get("token")}

    def logout(self) -> None:
        self._backend.logout()
        self._current_session = None

    def get_current_session(self):
        return self._current_session

    def is_authenticated(self) -> bool:
        return bool(self._backend.token and self._current_session)

    def get_current_token(self) -> Optional[str]:
        return self._backend.token

    def get_user_by_username(self, username: str):
        for user in self.list_users(include_inactive=True):
            if str(user.get("username", "")).lower() == str(username or "").lower():
                return user
        return None

    def get_user_by_id(self, user_id: Any):
        target = str(user_id)
        for user in self.list_users(include_inactive=True):
            if str(user.get("id") or user.get("_id")) == target:
                return user
        return None

    # ----------------------------- administration -----------------------------

    def list_users(self, include_inactive: bool = False):
        if not self.is_authenticated():
            return []
        data = self._backend.request(
            "GET",
            "/api/admin/users",
            {"include_inactive": include_inactive},
        ) if False else self._backend.request("GET", "/api/admin/users")
        users = data.get("users") or []
        if include_inactive:
            return users
        return [u for u in users if str(u.get("status", "active")).lower() == "active"]

    def list_employees(self):
        if not self.is_authenticated():
            return []
        data = self._backend.request("GET", "/api/admin/employees")
        return data.get("employees") or []

    def get_employee(self, employee_id: Any):
        target = str(employee_id)
        for employee in self.list_employees():
            if str(employee.get("employee_id") or employee.get("id") or employee.get("_id")) == target:
                return employee
        return None

    def create_user(
        self,
        employee_id: Any,
        username: str,
        password: str,
        role: str = "Staff",
        active: bool = True,
        require_password_change: bool = False,
    ):
        return self._backend.request(
            "POST",
            "/api/admin/users",
            {
                "employee_id": str(employee_id),
                "username": username,
                "password": password,
                "role": role,
                "active": bool(active),
                "require_password_change": bool(require_password_change),
            },
        ).get("user") or {}

    def update_user(self, user_id: Any, username: Optional[str] = None, role: Optional[str] = None, active: Optional[bool] = None, employee_id: Any = None):
        payload: dict[str, Any] = {}
        if username is not None:
            payload["username"] = username
        if role is not None:
            payload["role"] = role
        if active is not None:
            payload["active"] = bool(active)
        if employee_id is not None:
            payload["employee_id"] = str(employee_id)
        return self._backend.request(
            "PUT",
            f"/api/admin/users/{str(user_id)}",
            payload,
        ).get("user") or {}

    def reset_password(self, user_id: Any, password: str):
        return self._backend.request(
            "POST",
            f"/api/admin/users/{str(user_id)}/reset-password",
            {"password": password},
        ).get("user") or {}

    def delete_user(self, user_id: Any):
        return self._backend.request(
            "DELETE",
            f"/api/admin/users/{str(user_id)}",
        )