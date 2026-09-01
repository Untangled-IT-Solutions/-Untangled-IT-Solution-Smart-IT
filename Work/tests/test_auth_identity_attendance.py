"""Authentication/session tests for the Mongo-backed desktop architecture."""

from app.models.account import AuthSession, UserAccount
from app.models.role_permission import (
    can_access_module,
    can_administer_accounts,
    can_manage_attendance,
)
from app.services.auth_service import AuthService


class FakeMongoAuthService:
    def __init__(self) -> None:
        self.logged_out = False
        self.touched = False

    @staticmethod
    def hash_password(password: str) -> str:
        return f"hashed:{password}"

    @staticmethod
    def password_matches(password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"

    def logout(self) -> None:
        self.logged_out = True

    def touch_session(self) -> None:
        self.touched = True


def _session(role: str = "Operations Manager") -> AuthSession:
    account = UserAccount(
        id="user-1",
        employee_id="employee-1",
        username="ubuntu.hadebe@untangledits.co.za",
        full_name="Ubuntu Hadebe",
        role=role,
        status="active",
    )
    return AuthSession(
        id="session-1",
        account=account,
        login_at="2026-08-27T00:00:00+00:00",
        last_activity_at="2026-08-27T00:00:00+00:00",
    )


def test_set_session_exposes_authenticated_identity() -> None:
    auth = AuthService(mongo_auth_service=FakeMongoAuthService())

    auth.set_session(_session())

    assert auth.is_authenticated
    assert auth.current_employee_id == "employee-1"
    assert auth.current_username == "ubuntu.hadebe@untangledits.co.za"
    assert auth.current_role == "Operations Manager"


def test_logout_clears_session_and_delegates_backend_logout() -> None:
    mongo_auth = FakeMongoAuthService()
    auth = AuthService(mongo_auth_service=mongo_auth)
    auth.set_session(_session())

    auth.logout()

    assert not auth.is_authenticated
    assert auth.current_session is None
    assert mongo_auth.logged_out


def test_password_helpers_delegate_to_mongo_auth_service() -> None:
    auth = AuthService(mongo_auth_service=FakeMongoAuthService())

    password_hash = auth.hash_password("SecurePass123")

    assert password_hash != "SecurePass123"
    assert auth.verify_password("SecurePass123", password_hash)
    assert not auth.verify_password("wrong-password", password_hash)


def test_touch_session_updates_activity_and_delegates_backend_touch() -> None:
    mongo_auth = FakeMongoAuthService()
    auth = AuthService(mongo_auth_service=mongo_auth)
    auth.set_session(_session())
    previous = auth.current_session.last_activity_at

    auth.touch_session()

    assert auth.current_session.last_activity_at != previous
    assert mongo_auth.touched


def test_role_permissions_for_mongo_session_roles() -> None:
    assert can_manage_attendance("Operations Manager")
    assert can_administer_accounts("Operations Manager")
    assert can_access_module("Director", "Reports")
    assert can_access_module("Software Engineer", "Dashboard")
    assert not can_administer_accounts("Software Engineer")
