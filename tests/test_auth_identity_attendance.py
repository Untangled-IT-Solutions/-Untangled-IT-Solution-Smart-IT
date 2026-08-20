"""Authentication, identity, and role-aware attendance tests."""

from datetime import datetime, timedelta, timezone

import pytest

from app.controllers.attendance_controller import AttendanceController
from app.database.database import Database
from app.models.role_permission import can_access_module, can_administer_accounts, can_manage_attendance
from app.services.auth_service import AuthService
from app.services.attendance_service import AttendanceService
from app.services.people_service import PeopleService


def _services(tmp_path, password: str = "SecurePass123"):
    database = Database(tmp_path / "untangled_nexus.db")
    database.initialize()
    auth = AuthService(database)
    auth.bootstrap_employee_accounts(password)
    people = PeopleService(database)
    attendance = AttendanceService(database)
    return database, auth, people, attendance


def test_successful_login_sets_authenticated_identity_and_session(tmp_path) -> None:
    _database, auth, _people, _attendance = _services(tmp_path)

    session = auth.authenticate("ubuntu.hadebe", "SecurePass123")

    assert session.employee_id == 3
    assert session.account.full_name == "Ubuntu Hadebe"
    assert session.role == "Operations Manager"
    assert auth.current_employee_id == 3
    assert session.login_at


def test_failed_login_and_inactive_account_are_blocked(tmp_path) -> None:
    _database, auth, _people, _attendance = _services(tmp_path)

    with pytest.raises(ValueError):
        auth.authenticate("ubuntu.hadebe", "wrong-password")

    auth.authenticate("ubuntu.hadebe", "SecurePass123")
    auth.set_account_status(3, False)
    auth.logout()

    with pytest.raises(ValueError, match="inactive"):
        auth.authenticate("ubuntu.hadebe", "SecurePass123")


def test_passwords_are_hashed_and_verified_without_plaintext(tmp_path) -> None:
    database, auth, _people, _attendance = _services(tmp_path)

    with database.connection() as connection:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE username = ?;",
            ("ubuntu.hadebe",),
        ).fetchone()

    assert row is not None
    assert row["password_hash"] != "SecurePass123"
    assert row["password_hash"].startswith("pbkdf2_sha256$")
    assert auth.verify_password("SecurePass123", row["password_hash"])


def test_authenticated_employee_clock_in_break_and_clock_out(tmp_path, monkeypatch) -> None:
    _database, auth, people, attendance = _services(tmp_path)
    auth.authenticate("siyanda.nkosi", "SecurePass123")
    controller = AttendanceController(attendance, people, auth)
    utc_start = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(AttendanceService, "_now", staticmethod(lambda: utc_start))

    record = controller.clock_in()
    assert record.employee_id == auth.current_employee_id

    with pytest.raises(ValueError):
        controller.clock_in()

    controller.start_break()
    monkeypatch.setattr(AttendanceService, "_now", staticmethod(lambda: utc_start + timedelta(minutes=30)))
    after_break = controller.end_break()
    assert after_break.break_duration_minutes == 30

    monkeypatch.setattr(AttendanceService, "_now", staticmethod(lambda: utc_start + timedelta(hours=2)))
    clocked_out = controller.clock_out()
    assert not clocked_out.is_clocked_in
    assert clocked_out.hours_worked == 1.5


def test_employee_cannot_access_other_employee_attendance(tmp_path) -> None:
    _database, auth, people, attendance = _services(tmp_path)
    auth.authenticate("siyanda.nkosi", "SecurePass123")
    controller = AttendanceController(attendance, people, auth)

    assert not controller.can_manage_attendance()
    with pytest.raises(PermissionError):
        controller.get_today_record(1)
    with pytest.raises(PermissionError):
        controller.get_employees()


def test_management_attendance_visibility_and_director_access(tmp_path) -> None:
    _database, auth, people, attendance = _services(tmp_path)
    auth.authenticate("ubuntu.hadebe", "SecurePass123")
    manager_controller = AttendanceController(attendance, people, auth)

    assert manager_controller.can_manage_attendance()
    assert manager_controller.get_employees()
    assert isinstance(manager_controller.get_today_records(), list)

    auth.logout()
    auth.authenticate("zandile.johanna", "SecurePass123")
    assert can_manage_attendance(auth.current_role)
    assert can_access_module(auth.current_role, "Reports")


def test_role_permissions_and_account_admin_restrictions(tmp_path) -> None:
    _database, auth, _people, _attendance = _services(tmp_path)

    auth.authenticate("ubuntu.hadebe", "SecurePass123")
    assert can_administer_accounts(auth.current_role)
    auth.logout()

    auth.authenticate("siyanda.nkosi", "SecurePass123")
    assert can_access_module(auth.current_role, "Dashboard")
    assert not can_administer_accounts(auth.current_role)
    with pytest.raises(PermissionError):
        auth.set_account_status(1, False)
