"""MongoDB-only authentication/session state service.

This service intentionally contains NO SQLite code.

MongoDB authentication itself is performed by MongoAuthService.
This class maintains the application's current authenticated session
and provides compatibility methods used by the existing controllers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.models.account import AuthSession, UserAccount


class AuthService:
    """Application authentication/session state.

    MongoAuthService performs the actual MongoDB credential verification.
    AuthService stores the resulting AuthSession for the rest of the UI.
    """

    _ACTIVE = "active"
    _INACTIVE = "inactive"

    def __init__(
        self,
        database: Any = None,
        mongo_auth_service: Any = None,
    ) -> None:
        # Kept as an optional compatibility argument so existing
        # application startup code does not immediately break.
        #
        # IMPORTANT:
        # This value is never used.
        # No SQLite connection is opened.
        self._mongo_auth_service = mongo_auth_service
        self._current_session: Optional[AuthSession] = None

    # ------------------------------------------------------------------
    # CURRENT SESSION
    # ------------------------------------------------------------------

    @property
    def current_session(self) -> Optional[AuthSession]:
        return self._current_session

    @current_session.setter
    def current_session(self, value: Optional[AuthSession]) -> None:
        self._current_session = value

    @property
    def current_account(self) -> Optional[UserAccount]:
        if self._current_session is None:
            return None

        return self._current_session.account

    @property
    def current_employee_id(self) -> Any:
        if self._current_session is None:
            return None

        return self._current_session.employee_id

    @property
    def current_role(self) -> str:
        if self._current_session is None:
            return "Anonymous"

        return self._current_session.role

    @property
    def current_username(self) -> str:
        if self._current_session is None:
            return ""

        return self._current_session.username

    @property
    def is_authenticated(self) -> bool:
        return (
            self._current_session is not None
            and self._current_session.is_authenticated
        )

    # ------------------------------------------------------------------
    # SESSION SETUP
    # ------------------------------------------------------------------

    def set_session(self, session: AuthSession) -> None:
        """Set the active application session."""
        if not isinstance(session, AuthSession):
            raise TypeError("session must be an AuthSession instance.")

        self._current_session = session

    def set_current_session(self, session: Optional[AuthSession]) -> None:
        """Compatibility alias."""
        self._current_session = session

    # ------------------------------------------------------------------
    # LOGOUT
    # ------------------------------------------------------------------

    def logout(self) -> None:
        """Clear the current application session.

        MongoAuthService is responsible for persisting MongoDB session
        logout state.
        """
        if self._mongo_auth_service is not None:
            try:
                self._mongo_auth_service.logout()
            except Exception as exc:
                print(f"MongoDB logout warning: {exc}")

        self._current_session = None

    # ------------------------------------------------------------------
    # SESSION ACTIVITY
    # ------------------------------------------------------------------

    def touch_session(self) -> None:
        """Update the current session activity timestamp."""

        if self._current_session is None:
            return

        now = self._format_time(self._now())

        self._current_session.last_activity_at = now

        if self._mongo_auth_service is not None:
            try:
                self._mongo_auth_service.touch_session()
            except Exception as exc:
                print(f"MongoDB session activity warning: {exc}")

    # ------------------------------------------------------------------
    # PASSWORD HELPERS
    # ------------------------------------------------------------------

    def hash_password(self, password: str) -> str:
        """Delegate password hashing to MongoAuthService."""

        if self._mongo_auth_service is None:
            raise RuntimeError("MongoDB authentication service is unavailable.")

        return self._mongo_auth_service.hash_password(password)

    def verify_password(
        self,
        password: str,
        password_hash: str,
    ) -> bool:
        """Verify a password against a stored hash."""

        if self._mongo_auth_service is None:
            return False

        return self._mongo_auth_service.password_matches(
            password,
            password_hash,
        )

    # ------------------------------------------------------------------
    # TIME HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _format_time(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()