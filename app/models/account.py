"""Authentication and account identity models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UserAccount:
    """Application login account linked to one employee record."""

    id: int | None
    employee_id: int
    username: str
    full_name: str
    role: str
    status: str
    last_login_at: str = ""

    @property
    def is_active(self) -> bool:
        return self.status.lower() == "active"


@dataclass(frozen=True)
class AuthSession:
    """Current authenticated user session."""

    id: int
    account: UserAccount
    login_at: str
    last_activity_at: str
    logout_at: str = ""

    @property
    def employee_id(self) -> int:
        return self.account.employee_id

    @property
    def role(self) -> str:
        return self.account.role
