"""Backend authentication service – HTTPS API only (never connects to MongoDB)."""

from __future__ import annotations

from typing import Any, Optional
import hashlib
import secrets

from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class BackendAuthService:
    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend
        self._current: Optional[dict[str, Any]] = None

    @staticmethod
    def hash_password(password: str) -> str:
        iterations = 310_000
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), iterations
        ).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    @staticmethod
    def generate_secure_password(length: int = 14) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*"
        return "".join(secrets.choice(alphabet) for _ in range(max(12, length)))

    @staticmethod
    def generate_username(full_name: str) -> str:
        cleaned = "".join(
            c.lower() if c.isalnum() else " " for c in (full_name or "")
        ).split()
        if not cleaned:
            return f"user_{secrets.token_hex(4)}@untangledits.co.za"
        return f"{cleaned[0]}.{cleaned[-1]}@untangledits.co.za"

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        """Verify credentials with the backend. Never succeeds without a token + user."""
        username = (username or "").strip()
        if not username or not password:
            raise PermissionError("Username and password are required.")

        try:
            data = self._backend.login(username, password)
        except BackendAPIError as exc:
            # Normalise common auth failures to a clear message
            msg = str(exc) or "Invalid username or password."
            if getattr(exc, "status_code", None) == 401:
                msg = "Invalid username or password."
            raise PermissionError(msg) from exc

        token = data.get("token") or data.get("access_token")
        user = data.get("user") or data.get("account") or {}
        employee = data.get("employee") or {}

        if not token:
            raise PermissionError("Authentication failed: no session token received.")
        if not user and not employee:
            raise PermissionError("Authentication failed: no user profile received.")

        self._current = {
            "token": token,
            "user": user,
            "employee": employee,
            "raw": data,
        }
        return {
            "user": user,
            "employee": employee,
            "session": self._current,
            "token": token,
        }

    def logout(self) -> None:
        self._backend.logout()
        self._current = None

    @property
    def requires_password_change(self) -> bool:
        if not self._current:
            return False
        user = self._current.get("user") or {}
        raw = self._current.get("raw") or {}
        return bool(user.get("require_password_change") or raw.get("require_password_change"))

    def change_password(self, current_password: str, new_password: str) -> None:
        self._backend.change_password(current_password, new_password)
        if self._current:
            user = self._current.get("user") or {}
            user["require_password_change"] = False

    @property
    def current(self) -> Optional[dict[str, Any]]:
        return self._current

    # ------------------------------------------------------------------
    # Admin user/account management (via Backend API only)
    # ------------------------------------------------------------------

    def list_users(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        try:
            return self._backend.list_users(include_inactive=include_inactive)
        except BackendAPIError as exc:
            raise RuntimeError(str(exc)) from exc

    def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        try:
            return self._backend.get_user(user_id)
        except BackendAPIError:
            return None

    def list_employees(self) -> list[dict[str, Any]]:
        try:
            return self._backend.list_admin_employees()
        except BackendAPIError as exc:
            raise RuntimeError(str(exc)) from exc

    def get_employee(self, employee_id: str) -> Optional[dict[str, Any]]:
        try:
            return self._backend.get_admin_employee(employee_id)
        except BackendAPIError:
            return None

    def create_user(
        self,
        employee_id: str,
        username: str,
        password: str,
        role: str,
        active: bool = True,
        require_password_change: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "employee_id": employee_id,
            "username": username,
            "password": password,
            "role": role,
            "active": active,
            "status": "active" if active else "inactive",
            "require_password_change": require_password_change,
        }
        try:
            return self._backend.create_user(payload)
        except BackendAPIError as exc:
            raise RuntimeError(str(exc)) from exc

    def update_user(self, user_id: str, **fields: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if "active" in fields:
            payload["active"] = fields["active"]
            payload["status"] = "active" if fields["active"] else "inactive"
        if "role" in fields and fields["role"] is not None:
            payload["role"] = fields["role"]
        if "username" in fields and fields["username"] is not None:
            payload["username"] = fields["username"]
        for key in ("email", "full_name", "status"):
            if key in fields and fields[key] is not None:
                payload[key] = fields[key]
        try:
            return self._backend.update_user(user_id, payload)
        except BackendAPIError as exc:
            raise RuntimeError(str(exc)) from exc

    def reset_password(self, user_id: str, password: str) -> dict[str, Any]:
        try:
            return self._backend.reset_user_password(user_id, password)
        except BackendAPIError as exc:
            raise RuntimeError(str(exc)) from exc

    def delete_user(self, user_id: str) -> None:
        try:
            self._backend.delete_user(user_id)
        except BackendAPIError as exc:
            raise RuntimeError(str(exc)) from exc
