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

    def login(self, username: str, password: str) -> tuple[bool, str]:
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

            self._on_success()
            return True, ""

        except PermissionError as error:
            return False, str(error) or "Invalid username or password."
        except BackendAPIError as error:
            return False, str(error) or "Could not reach the authentication server."
        except Exception as error:
            return False, f"Login failed: {error}"
