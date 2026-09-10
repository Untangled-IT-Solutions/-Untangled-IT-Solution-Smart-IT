# app/controllers/attendance_controller.py
"""Attendance controller."""

from app.services.attendance_service import AttendanceService
from app.services.people_service import PeopleService


class AttendanceController:
    """Controls attendance operations."""

    def __init__(
        self,
        attendance_service: AttendanceService,
        people_service: PeopleService,
    ) -> None:
        self._service = attendance_service
        self._people_service = people_service

    def get_employees(self) -> list:
        """Get list of employees."""
        return self._people_service.get_employees()

    def current_employee(self):
        """Get current employee."""
        return self._people_service.current_employee()

    def can_manage_attendance(self) -> bool:
        """Check if current user can manage attendance."""
        return self._service.can_manage_attendance()

    def get_attendance_status(self, employee_id: int) -> dict:
        """Return current attendance/timer state and punctuality."""
        return self._service.get_attendance_status(employee_id)

    def get_today_record(self, employee_id: int):
        """Get today's attendance record."""
        return self._service.get_today_record(employee_id)

    def get_today_records(self) -> list:
        """Get all today's attendance records."""
        return self._service.get_today_records()

    def get_live_hours(self, record) -> float:
        """Get live hours for a record."""
        return self._service.get_live_hours(record)

    def get_weekly_total(self, employee_id: int) -> float:
        """Get weekly total hours for an employee."""
        return self._service.get_weekly_total(employee_id)

    def get_monthly_total(self, employee_id: int) -> float:
        """Get monthly total hours for an employee."""
        return self._service.get_monthly_total(employee_id)

    def get_weekly_timesheet(self, employee_id: int) -> list:
        """Get weekly timesheet for an employee."""
        return self._service.get_weekly_timesheet(employee_id)

    def clock_in(self, employee_id: int) -> dict:
        """Clock in an employee."""
        return self._service.clock_in(employee_id)

    def clock_out(self, employee_id: int) -> dict:
        """Clock out an employee."""
        return self._service.clock_out(employee_id)

    def start_break(self, employee_id: int) -> dict:
        """Start a break."""
        return self._service.start_break(employee_id)

    def end_break(self, employee_id: int) -> dict:
        """End a break."""
        return self._service.end_break(employee_id)