"""Attendance service tests."""

from datetime import datetime, timedelta, timezone

from app.database.database import Database
from app.services.attendance_service import AttendanceService
from tests.helpers import seeded_employees


def test_attendance_clock_in_stores_utc_timestamps_and_calculates_live_hours(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "untangled_nexus.db")
    database.initialize()
    employee = seeded_employees(database)[0]
    utc_start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(AttendanceService, "_now", staticmethod(lambda: utc_start))
    service = AttendanceService(database)

    record = service.clock_in(employee.id)
    assert record.clock_in_at == "2024-01-01 12:00:00"
    assert record.created_at == "2024-01-01 12:00:00"
    assert record.updated_at == "2024-01-01 12:00:00"
    assert record.is_clocked_in

    service.start_break(employee.id)
    monkeypatch.setattr(AttendanceService, "_now", staticmethod(lambda: utc_start + timedelta(minutes=15)))
    after_break = service.end_break(employee.id)
    assert after_break.break_duration_minutes == 15
    assert after_break.break_started_at == ""

    monkeypatch.setattr(AttendanceService, "_now", staticmethod(lambda: utc_start + timedelta(minutes=90)))
    clocked_out = service.clock_out(employee.id)
    assert not clocked_out.is_clocked_in
    assert clocked_out.hours_worked == 1.25
    assert clocked_out.clock_out_at == "2024-01-01 13:30:00"


def test_attendance_clock_actions_generate_timesheet_totals(tmp_path) -> None:
    database = Database(tmp_path / "untangled_nexus.db")
    database.initialize()
    employee = seeded_employees(database)[0]
    service = AttendanceService(database)

    clocked_in = service.clock_in(employee.id)
    assert clocked_in.is_clocked_in

    service.start_break(employee.id)
    after_break = service.end_break(employee.id)
    clocked_out = service.clock_out(employee.id)

    assert after_break.break_started_at == ""
    assert not clocked_out.is_clocked_in
    assert service.get_weekly_total(employee.id) >= 0
    assert service.get_monthly_total(employee.id) >= 0
