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
        return self._people_service.get_employees()

    def current_employee(self):
        return self._people_service.current_employee()

    def can_manage_attendance(self) -> bool:
        return self._service.can_manage_attendance()

    def status(self):
        return self._service.status()

    def clock_in(self, employee_id=None):
        return self._service.clock_in(employee_id)

    def clock_out(self, employee_id=None):
        return self._service.clock_out(employee_id)

    def break_start(self, employee_id=None):
        return self._service.break_start(employee_id)

    def break_end(self, employee_id=None):
        return self._service.break_end(employee_id)

    def get_today(self, employee_id=None):
        return self._service.get_today(employee_id)

    def get_history(self, employee_id=None, days: int = 30):
        return self._service.get_history(employee_id, days)
