"""Settings controller – Backend API only (no local database)."""

from __future__ import annotations

from typing import Any, Optional

from app.models.account import UserAccount
from app.models.role_permission import can_administer_accounts
from app.services.auth_service import AuthService
from app.services.people_service import PeopleService
from app.utils.config import API_BASE_URL, APP_VERSION, COMPANY_LEGAL_NAME, COMPANY_NAME
from app.utils.theme import Theme


class SettingsController:
    """Provides application settings and theme preference actions."""

    def __init__(
        self,
        auth_service: AuthService,
        people_service: PeopleService,
        backend: Any = None,
        on_check_for_updates: Any = None,
        **_kwargs: Any,
    ) -> None:
        self._auth_service = auth_service
        self._people_service = people_service
        self._backend = backend
        self._on_check_for_updates = on_check_for_updates

    def check_for_updates(self) -> None:
        """Trigger a manual update check (shows up-to-date dialog if current)."""
        callback = self._on_check_for_updates
        if callable(callback):
            callback(True)

    def get_theme_mode(self) -> str:
        return getattr(Theme, "CURRENT_MODE", "dark")

    def set_theme_mode(self, mode: str) -> str:
        apply = getattr(Theme, "apply_mode", None)
        if callable(apply):
            return apply(mode, persist=True)
        return mode

    def get_settings(self) -> dict[str, str]:
        backend_url = API_BASE_URL
        if self._backend is not None:
            backend_url = getattr(self._backend, "base_url", API_BASE_URL) or API_BASE_URL
        return {
            "Company": COMPANY_LEGAL_NAME,
            "Platform": COMPANY_NAME,
            "Working Hours": "08:00 - 17:00",
            "Notifications": "Enabled",
            "Application Version": APP_VERSION,
            "Backend": str(backend_url),
            "Data Source": "Backend API (MongoDB on server only)",
        }

    def can_administer_accounts(self) -> bool:
        session = getattr(self._auth_service, "current_session", None)
        role = ""
        if session is not None:
            role = getattr(session, "role", "") or ""
            account = getattr(session, "account", None)
            if account is not None and not role:
                role = getattr(account, "role", "") or ""
        try:
            return can_administer_accounts(role)
        except Exception:
            return str(role).strip().lower() in {
                "director",
                "operations manager",
            }

    def get_accounts(self) -> list:
        return []

    def get_employee_options(self) -> list[str]:
        try:
            employees = self._people_service.get_employees() or []
        except Exception:
            employees = []
        options = []
        for employee in employees:
            if isinstance(employee, dict):
                eid = employee.get("employee_id") or employee.get("id") or ""
                name = employee.get("full_name") or employee.get("name") or ""
            else:
                eid = getattr(employee, "id", "") or ""
                name = getattr(employee, "full_name", "") or ""
            if eid or name:
                options.append(f"{eid}: {name}".strip(": "))
        return options or ["No employees"]

    def get_role_options(self) -> list[str]:
        return [
            "Director",
            "Business Lead",
            "Operations Manager",
            "Staff",
            "Intern",
        ]

    def create_account(
        self,
        employee_option: str,
        username: str,
        password: str,
        role: str,
        active: bool,
    ) -> Any:
        raise RuntimeError(
            "Create accounts from User Management. Settings no longer writes to a local database."
        )

    def reset_password(self, account_id: int, password: str) -> None:
        raise RuntimeError("Use User Management to reset passwords.")

    def set_account_status(self, account_id: int, active: bool) -> None:
        raise RuntimeError("Use User Management to change account status.")

    def change_role(self, account_id: int, role: str) -> None:
        raise RuntimeError("Use User Management to change roles.")
