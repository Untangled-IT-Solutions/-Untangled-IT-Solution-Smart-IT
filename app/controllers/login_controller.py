# app/controllers/login_controller.py
"""Login controller."""

from collections.abc import Callable
from typing import Optional

from app.services.auth_service import AuthService
from app.services.mongo_auth_service import MongoAuthService


class LoginController:
    """Handles login actions requested by the login view with dual auth support."""

    def __init__(
        self,
        auth_service: AuthService,
        on_success: Callable[[], None],
        mongo_auth_service: Optional[MongoAuthService] = None,
    ) -> None:
        self._auth_service = auth_service
        self._on_success = on_success
        self._mongo_auth = mongo_auth_service

    @property
    def mongo_auth(self) -> Optional[MongoAuthService]:
        """Return the optional MongoDB authentication service."""
        return self._mongo_auth

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """Authenticate credentials and trigger the next app state."""
        # Try MongoDB authentication first if available
        if self._mongo_auth:
            try:
                print(f"🔄 Attempting MongoDB login for: {username}")
                user = self._mongo_auth.authenticate(username, password)
                print(f"✅ MongoDB login successful for: {username}")
                # Store the user in the auth service for session management
                self._auth_service._current_session = self._create_session_from_mongo_user(user)
                self._on_success()
                return True, ""
            except (ValueError, PermissionError) as error:
                print(f"❌ MongoDB login failed: {error}")
                # If MongoDB auth fails, try SQLite auth
                pass
        
        # Fallback to SQLite authentication
        try:
            print(f"🔄 Attempting SQLite login for: {username}")
            self._auth_service.authenticate(username, password)
            print(f"✅ SQLite login successful for: {username}")
        except ValueError as error:
            print(f"❌ SQLite login failed: {error}")
            return False, str(error)
        else:
            self._on_success()
            return True, ""
    
    def _create_session_from_mongo_user(self, user: dict):
        """Create a session object from MongoDB user data."""
        from app.models.account import UserAccount, AuthSession
        
        # Create a UserAccount from MongoDB user
        account = UserAccount(
            id=user.get('_id'),
            employee_id=user.get('employee_id'),
            username=user.get('username'),
            full_name=user.get('full_name'),
            role=user.get('role'),
            status=user.get('status'),
            last_login_at=user.get('last_login_at', ''),
        )
        
        # Create an AuthSession
        session = AuthSession(
            id=1,  # Placeholder ID
            account=account,
            login_at=user.get('last_login_at', ''),
            last_activity_at='',
        )
        return session
