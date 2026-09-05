"""Session & authentication state (Backend / MongoDB only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.models.account import AuthSession, UserAccount
from app.services.backend_auth_service import BackendAuthService


class AuthService:
    """Holds the current authenticated session for the desktop client."""

    def __init__(self, mongo_auth: BackendAuthService) -> None:
        self._mongo_auth = mongo_auth
        self._current_session: Optional[AuthSession] = None

    @property
    def current_session(self) -> Optional[AuthSession]:
        return self._current_session

    @current_session.setter
    def current_session(self, value: Optional[AuthSession]) -> None:
        self._current_session = value

    @property
    def is_authenticated(self) -> bool:
        if self._current_session is None:
            return False
        if not getattr(self._current_session, "token", None):
            return False
        return bool(self._current_session.is_authenticated)


    @property
    def current_user(self) -> Optional[UserAccount]:
        if self._current_session:
            return self._current_session.account
        return None

    def set_session_from_mongo(self, authentication: dict[str, Any]) -> AuthSession:
        """Build and store an AuthSession from a successful backend login response."""
        user_data = authentication.get("user") or authentication.get("account") or {}
        employee = authentication.get("employee") or {}
        token = authentication.get("token") or authentication.get("access_token")
        if not token:
            raise PermissionError("Cannot create session without an authentication token.")
        if not user_data and not employee:
            raise PermissionError("Cannot create session without user details.")
        now = datetime.now(timezone.utc).isoformat()

        account = UserAccount(
            id=user_data.get("id") or user_data.get("_id") or employee.get("id"),
            employee_id=employee.get("employee_id")
            or employee.get("id")
            or user_data.get("employee_id"),
            username=user_data.get("username") or user_data.get("email") or "",
            full_name=user_data.get("full_name")
            or employee.get("full_name")
            or user_data.get("name")
            or "",
            role=user_data.get("role") or employee.get("role") or "employee",
            status=user_data.get("status") or "active",
            department=user_data.get("department") or employee.get("department"),
            email=user_data.get("email") or employee.get("email"),
            last_login_at=now,
        )

        session = AuthSession(
            id=token or account.id,
            account=account,
            login_at=now,
            last_activity_at=now,
            token=token,
            raw=authentication,
        )
        self._current_session = session
        return session

    def logout(self) -> None:
        try:
            self._mongo_auth.logout()
        finally:
            self._current_session = None
