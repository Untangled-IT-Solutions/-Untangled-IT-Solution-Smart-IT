"""Account and authentication session models.

MongoDB-only application models.
No SQLite dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class UserAccount:
    """Authenticated user account."""

    id: Any
    employee_id: Any
    username: str
    full_name: str
    role: str
    status: str = "active"
    last_login_at: str = ""

    @property
    def is_active(self) -> bool:
        return str(self.status).strip().lower() in {
            "active",
            "enabled",
            "approved",
        }

    @property
    def is_admin(self) -> bool:
        return self.role in {
            "Director",
            "Branch Manager",
            "Operations Manager",
            "Administrator",
            "Admin",
            "Super Admin",
        }

    @property
    def surname(self) -> str:
        parts = str(self.full_name or "").strip().split()
        return parts[-1] if parts else ""

    @property
    def first_name(self) -> str:
        parts = str(self.full_name or "").strip().split()
        return parts[0] if parts else ""


@dataclass
class AuthSession:
    """Current authenticated application session."""

    id: Any
    account: UserAccount
    login_at: str
    last_activity_at: str

    @property
    def employee_id(self) -> Any:
        return self.account.employee_id

    @property
    def username(self) -> str:
        return self.account.username

    @property
    def role(self) -> str:
        return self.account.role

    @property
    def full_name(self) -> str:
        return self.account.full_name

    @property
    def status(self) -> str:
        return self.account.status

    @property
    def is_authenticated(self) -> bool:
        return bool(self.account and self.account.is_active)
