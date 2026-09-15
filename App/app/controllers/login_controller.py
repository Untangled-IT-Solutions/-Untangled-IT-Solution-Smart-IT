"""Login controller – Backend auth only. No guest / offline login."""

from __future__ import annotations

from collections.abc import Callable

from app.services.auth_service import AuthService
from app.services.mongo_auth_service import MongoAuthService
from app.services.backend_api_client import BackendAPIError


class LoginController:
    """Authenticate users via Backend API only."""

    def __init__(
        self,
        auth_service: AuthService,
        mongo_auth_service: MongoAuthService,
        on_success: Callable[[], None],
    ) -> None:
        self._auth_service = auth_service
        self._mongo_auth = mongo_auth_service
        self._on_success = on_success

    def login(self, username: str, password: str, *, notify_success: bool = True) -> tuple[bool, str]:
        username = (username or "").strip()
        if not username or not password:
            return False, "Please enter both username and password."

        if self._mongo_auth is None:
            return False, "Authentication service is not available."

        try:
            authentication = self._mongo_auth.authenticate(username, password)

            # Double-check we received a usable session before opening the app
            token = authentication.get("token")
            user = authentication.get("user") or {}
            employee = authentication.get("employee") or {}
            if not token:
                return False, "Login failed: no authentication token."
            if not user and not employee:
                return False, "Login failed: no user profile."

            self._auth_service.set_session_from_mongo(authentication)

            if not self._auth_service.is_authenticated:
                return False, "Login failed: session could not be established."

            if notify_success:
                self._on_success()
            return True, ""

        except PermissionError as error:
            return False, str(error) or "Invalid username or password."
        except BackendAPIError as error:
            return False, str(error) or "Could not reach the authentication server."
        except Exception as error:
            return False, f"Login failed: {error}"

    def complete_login(self) -> None:
        """Deliver the authenticated transition on the UI thread."""
        self._on_success()

    @property
    def requires_password_change(self) -> bool:
        return bool(self._mongo_auth and self._mongo_auth.requires_password_change)

    def change_password(self, current_password: str, new_password: str) -> tuple[bool, str]:
        try:
            self._mongo_auth.change_password(current_password, new_password)
            return True, ""
        except (PermissionError, BackendAPIError) as error:
            return False, str(error) or "Password change failed."
        except Exception as error:
            return False, f"Password change failed: {error}"

    def cancel_pending_login(self) -> None:
        """Revoke a temporary session when first-login setup is cancelled."""
        try:
            self._auth_service.logout()
        except Exception:
            pass
