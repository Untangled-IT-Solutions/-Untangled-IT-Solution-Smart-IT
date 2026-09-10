"""Login controller - MongoDB only."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional

from app.models.account import AuthSession, UserAccount
from app.services.auth_service import AuthService
from app.services.mongo_auth_service import MongoAuthService


class LoginController:
    """Authenticate users using MongoDB only."""

    def __init__(
        self,
        auth_service: AuthService,
        on_success: Callable[[], None],
        mongo_auth_service: Optional[MongoAuthService] = None,
    ) -> None:
        self._auth_service = auth_service
        self._mongo_auth = mongo_auth_service
        self._on_success = on_success
        self._using_mongo_session = False

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """Authenticate credentials using MongoDB."""
        username = username.strip()

        # MUST use MongoDB - no SQLite fallback
        if not self._mongo_auth:
            return False, "MongoDB authentication is not available."

        try:
            authentication = self._mongo_auth.authenticate(username, password)

            self._auth_service._current_session = (
                self._create_session_from_mongo_response(authentication)
            )
            self._using_mongo_session = True
            self._on_success()
            return True, ""

        except ValueError as error:
            # Authentication failed - wrong password or user doesn't exist
            return False, str(error)
        except PermissionError as error:
            return False, str(error)
        except Exception as error:
            print(f"MongoDB login error: {error}")
            return False, f"Login error: {error}"

    def _create_session_from_mongo_response(
        self,
        authentication: dict[str, Any],
    ) -> AuthSession:
        """
        MongoAuthService returns:
        {"user": ..., "employee": ..., "session": ..., "token": ...}
        """
        user = authentication.get("user") or {}
        employee = authentication.get("employee") or {}
        mongo_session = authentication.get("session") or {}

        employee_value = (
            employee.get("sqlite_id")
            or user.get("sqlite_employee_id")
            or user.get("employee_id")
            or 0
        )

        if employee_value is None or employee_value == "":
            employee_id = None
        else:
            try:
                employee_id = int(employee_value)
            except (TypeError, ValueError):
                employee_id = str(employee_value)

        login_time = self._format_datetime(
            mongo_session.get("login_at") or user.get("last_login_at")
        )

        account = UserAccount(
            id=None,
            employee_id=employee_id,
            username=str(user.get("username") or ""),
            full_name=str(
                user.get("full_name")
                or employee.get("full_name")
                or "Untangled User"
            ),
            role=str(user.get("role") or "Staff"),
            status=str(user.get("status") or "active"),
            last_login_at=login_time,
        )

        return AuthSession(
            id=0,
            account=account,
            login_at=login_time,
            last_activity_at=login_time,
        )

    def logout(self) -> None:
        """Close the active session."""
        if self._using_mongo_session and self._mongo_auth:
            try:
                self._mongo_auth.logout()
            except Exception as error:
                print(f"MongoDB logout error: {error}")

            self._auth_service._current_session = None
            self._using_mongo_session = False
            return

        try:
            self._auth_service.logout()
        except Exception as error:
            print(f"SQLite logout error: {error}")

    @staticmethod
    def _format_datetime(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)