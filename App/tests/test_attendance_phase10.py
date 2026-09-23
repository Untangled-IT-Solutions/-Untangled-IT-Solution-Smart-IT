from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.controllers.attendance_controller import AttendanceController
from app.services.mongo_attendance_service import MongoAttendanceService


class Backend:
    pass


class Attendance:
    def get_team_today(self):
        return []

    def get_working_now(self):
        return {"count": 0}


class People:
    def get_employees(self):
        return []

    def current_employee(self):
        return None


def controller(role):
    account = SimpleNamespace(role=role)
    return AttendanceController(Attendance(), People(), lambda: account)


def test_team_attendance_permission_matches_server_roles():
    for role in ("Director", "Business Lead", "Operations Manager", "Super Admin"):
        assert controller(role).can_manage_attendance() is True
    for role in ("Branch Manager", "Staff", "Intern"):
        assert controller(role).can_manage_attendance() is False


def test_live_work_time_freezes_during_break_and_uses_closed_total():
    service = MongoAttendanceService(Backend())
    current = datetime.now(timezone.utc)
    record = {
        "clock_in_at": (current - timedelta(hours=2)).isoformat(),
        "break_started_at": (current - timedelta(hours=1)).isoformat(),
        "break_seconds": 0,
    }
    elapsed = service.get_live_seconds(record)
    assert 3598 <= elapsed <= 3602

    closed = dict(record, clock_out_at=current.isoformat(), work_seconds=2750)
    assert service.get_live_seconds(closed) == 2750
