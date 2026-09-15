"""User Management controller backed exclusively by the authenticated API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.auth_service import AuthService
from app.services.backend_auth_service import BackendAuthService


class UserManagementController:
    _ADMIN_ROLES = {"Director", "Branch Manager", "Operations Manager", "Super Admin"}

    def __init__(self, mongo_auth_service: Optional[BackendAuthService], people_service: Any = None, auth_service: Optional[AuthService] = None) -> None:
        self._mongo_auth = mongo_auth_service
        self._auth_service = auth_service

    def require_admin(self) -> bool:
        if self._auth_service is None or self._auth_service.current_session is None:
            return False
        return str(self._auth_service.current_session.role).strip().lower() in {r.lower() for r in self._ADMIN_ROLES}

    def _require_admin(self) -> None:
        if not self.require_admin():
            raise PermissionError("Only an administrator may manage user accounts.")

    def _service(self) -> BackendAuthService:
        if self._mongo_auth is None:
            raise RuntimeError("Backend authentication service is unavailable.")
        return self._mongo_auth

    def get_all_users(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        self._require_admin()
        return self._service().list_users(include_inactive=include_inactive)

    def get_user_statistics(self) -> Dict[str, Any]:
        users = self.get_all_users(include_inactive=True)
        active = [u for u in users if str(u.get("status", "")).lower() in {"active", "enabled", "approved"}]
        inactive = [u for u in users if u not in active]
        login_values = [str(u.get("last_login_at")) for u in users if u.get("last_login_at")]
        return {
            "total_users": len(users),
            "active_users": len(active),
            "inactive_users": len(inactive),
            "last_login": max(login_values) if login_values else None,
        }

    def get_employees_without_accounts(self) -> List[Dict[str, Any]]:
        self._require_admin()
        return self._service().list_employees()

    def get_employee_by_id(self, employee_id: str):
        self._require_admin()
        return self._service().get_employee(employee_id)

    def create_user_with_password(self, employee_id: str, username: str, password: str, role: str, active: bool = True):
        self._require_admin()
        if not password:
            raise ValueError("Password is required.")
        employee = self._service().get_employee(employee_id)
        if not employee:
            raise ValueError("Employee not found in MongoDB.")
        existing = next((u for u in self._service().list_users(include_inactive=True) if str(u.get("employee_id")) == str(employee_id)), None)
        if existing:
            return self._service().update_user(existing.get("id") or existing.get("_id"), username=username, role=role, active=active)
        return self._service().create_user(employee_id, username, password, role, active)

    def create_user_with_generated_password(self, employee_id: str, username: str, role: str, active: bool = True):
        self._require_admin()
        password = self._service().generate_secure_password()
        employee = self._service().get_employee(employee_id)
        if not employee:
            raise ValueError("Employee not found in MongoDB.")
        existing = next((u for u in self._service().list_users(include_inactive=True) if str(u.get("employee_id")) == str(employee_id)), None)
        if existing:
            user = self._service().update_user(existing.get("id") or existing.get("_id"), username=username or None, role=role, active=active)
            # Existing account needs an explicit password reset.
            self._service().reset_password(existing.get("id") or existing.get("_id"), password)
        else:
            user = self._service().create_user(employee_id, username, password, role, active, require_password_change=True)
        return user, password

    def create_user_from_employee(self, employee_id: str, role: str = "Staff", active: bool = True):
        self._require_admin()
        employee = self._service().get_employee(employee_id)
        if not employee:
            raise ValueError("Employee not found in MongoDB.")
        full_name = employee.get("full_name") or " ".join(filter(None, [employee.get("first_name"), employee.get("surname") or employee.get("last_name")]))
        username = self._service().generate_username(full_name)
        existing_names = {str(u.get("username", "")).lower() for u in self._service().list_users(include_inactive=True)}
        base = username
        counter = 2
        while username.lower() in existing_names:
            local, _, domain = base.partition("@")
            username = f"{local}{counter}@{domain}" if domain else f"{local}{counter}"
            counter += 1
        return self.create_user_with_generated_password(employee_id, username, role, active)

    def reset_user_password_generated(self, user_id: str) -> str:
        self._require_admin()
        user = self._service().get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        password = self._service().generate_secure_password()
        self._service().reset_password(user_id, password)
        return password

    def set_user_status(self, user_id: str, active: bool) -> None:
        self._require_admin()
        user = self._service().get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        self._service().update_user(user_id, active=active)

    def delete_user(self, user_id: str) -> None:
        self._require_admin()
        current = self._auth_service.current_session if self._auth_service else None
        if current and str(getattr(current, "user_id", "")) == str(user_id):
            raise ValueError("You cannot delete your own account while logged in.")
        user = self._service().get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        self._service().delete_user(user_id)
