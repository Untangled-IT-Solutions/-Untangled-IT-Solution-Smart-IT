# app/controllers/attendance_controller.py
"""Attendance controller."""

from typing import Optional

from app.models.attendance import AttendanceRecord
from app.models.employee import Employee
from app.models.role_permission import can_manage_attendance
from app.services.auth_service import AuthService
from app.services.attendance_service import AttendanceService
from app.services.people_service import PeopleService
from app.services.mongo_attendance_service import MongoAttendanceService


class AttendanceController:
    """Coordinates attendance actions and employee selection for the view layer."""

    def __init__(
        self,
        attendance_service: AttendanceService,
        people_service: PeopleService,
        auth_service: AuthService,
        mongo_attendance_service: Optional[MongoAttendanceService] = None,  # Make optional
    ) -> None:
        self._attendance_service = attendance_service
        self._people_service = people_service
        self._auth_service = auth_service
        self._mongo_attendance = mongo_attendance_service

    def get_employees(self) -> list[Employee]:
        self._require_management()
        return self._people_service.get_employees()

    def can_manage_attendance(self) -> bool:
        return can_manage_attendance(self._auth_service.current_role)

    def current_employee(self) -> Employee:
        session = self._auth_service.require_authenticated()
        employee = self._people_service.get_employee(session.employee_id)
        if employee is None:
            raise ValueError("Authenticated employee was not found.")
        return employee

    def clock_in(self, employee_id: int | None = None) -> AttendanceRecord:
        employee_id = self._authorized_employee_id(employee_id)
        return self._attendance_service.clock_in(employee_id)

    def clock_out(self, employee_id: int | None = None) -> AttendanceRecord:
        employee_id = self._authorized_employee_id(employee_id)
        return self._attendance_service.clock_out(employee_id)

    def start_break(self, employee_id: int | None = None) -> AttendanceRecord:
        employee_id = self._authorized_employee_id(employee_id)
        return self._attendance_service.start_break(employee_id)

    def end_break(self, employee_id: int | None = None) -> AttendanceRecord:
        employee_id = self._authorized_employee_id(employee_id)
        return self._attendance_service.end_break(employee_id)

    def get_today_record(self, employee_id: int | None = None) -> AttendanceRecord | None:
        employee_id = self._authorized_employee_id(employee_id)
        return self._attendance_service.get_today_record(employee_id)

    def get_today_records(self) -> list[AttendanceRecord]:
        self._require_management()
        return self._attendance_service.get_today_records()

    def get_weekly_timesheet(self, employee_id: int | None = None) -> list[AttendanceRecord]:
        employee_id = self._authorized_employee_id(employee_id)
        return self._attendance_service.get_weekly_timesheet(employee_id)

    def get_weekly_total(self, employee_id: int | None = None) -> float:
        """Return weekly total and include current live hours for an active record so the UI shows up-to-date totals."""
        employee_id = self._authorized_employee_id(employee_id)
        base_total = self._attendance_service.get_weekly_total(employee_id)
        today_record = self._attendance_service.get_today_record(employee_id)
        if today_record is not None and today_record.is_clocked_in:
            # Add live (in-progress) hours for today to the stored weekly total
            live_hours = self._attendance_service.get_live_hours(today_record)
            return round(base_total + live_hours, 2)
        return base_total

    def get_monthly_total(self, employee_id: int | None = None) -> float:
        employee_id = self._authorized_employee_id(employee_id)
        return self._attendance_service.get_monthly_total(employee_id)

    def get_live_hours(self, record: AttendanceRecord) -> float:
        self._authorized_employee_id(record.employee_id)
        return self._attendance_service.get_live_hours(record)

    def get_live_seconds(self, record: AttendanceRecord) -> int:
        """Return exact net worked seconds for the attendance-page timer."""
        self._authorized_employee_id(record.employee_id)
        return self._attendance_service.get_live_seconds(record)

    def get_live_break_seconds(self, record: AttendanceRecord) -> int:
        """Return used break seconds, capped at the one-hour daily allowance."""
        self._authorized_employee_id(record.employee_id)
        return self._attendance_service.get_live_break_seconds(record)

    # MongoDB Timer Methods
    def get_timer_status(self, employee_id: int) -> dict:
        """Get current timer status using MongoDB."""
        if not self._mongo_attendance:
            return {"status": "not_available"}
        
        # Convert SQLite employee_id to MongoDB ObjectId
        mongo_id = self._get_mongo_employee_id(employee_id)
        if not mongo_id:
            return {"status": "employee_not_found"}
        
        return self._mongo_attendance.get_timer_status(mongo_id)

    def clock_in_mongo(self, employee_id: int) -> dict:
        """Clock in using MongoDB timer."""
        if not self._mongo_attendance:
            raise ValueError("MongoDB timer not available.")
        
        employee = self._people_service.get_employee(employee_id)
        if not employee:
            raise ValueError("Employee not found.")
        
        mongo_id = self._get_mongo_employee_id(employee_id)
        if not mongo_id:
            raise ValueError("Employee not found in MongoDB.")
        
        return self._mongo_attendance.clock_in(mongo_id, employee.full_name)

    def clock_out_mongo(self, employee_id: int) -> dict:
        """Clock out using MongoDB timer."""
        if not self._mongo_attendance:
            raise ValueError("MongoDB timer not available.")
        
        mongo_id = self._get_mongo_employee_id(employee_id)
        if not mongo_id:
            raise ValueError("Employee not found in MongoDB.")
        
        return self._mongo_attendance.clock_out(mongo_id)

    def start_break_mongo(self, employee_id: int) -> dict:
        """Start break using MongoDB timer."""
        if not self._mongo_attendance:
            raise ValueError("MongoDB timer not available.")
        
        mongo_id = self._get_mongo_employee_id(employee_id)
        if not mongo_id:
            raise ValueError("Employee not found in MongoDB.")
        
        return self._mongo_attendance.start_break(mongo_id)

    def end_break_mongo(self, employee_id: int) -> dict:
        """End break using MongoDB timer."""
        if not self._mongo_attendance:
            raise ValueError("MongoDB timer not available.")
        
        mongo_id = self._get_mongo_employee_id(employee_id)
        if not mongo_id:
            raise ValueError("Employee not found in MongoDB.")
        
        return self._mongo_attendance.end_break(mongo_id)

    def _get_mongo_employee_id(self, sqlite_employee_id: int):
        """Convert SQLite employee ID to MongoDB ObjectId."""
        if not self._mongo_attendance:
            return None
        
        employee = self._people_service.get_employee(sqlite_employee_id)
        if not employee:
            return None
        
        # Look up in MongoDB by employee_number or email
        try:
            mongo_employees = self._mongo_attendance._mongo.get_collection("employees")
            mongo_emp = mongo_employees.find_one({
                "$or": [
                    {"employee_number": employee.employee_number},
                    {"email": employee.email},
                ]
            })
            return mongo_emp["_id"] if mongo_emp else None
        except Exception:
            return None

    def _authorized_employee_id(self, employee_id: int | None = None) -> int:
        session = self._auth_service.require_authenticated()
        requested_id = employee_id if employee_id is not None else session.employee_id
        if requested_id != session.employee_id and not can_manage_attendance(session.role):
            raise PermissionError("You can only access your own attendance.")
        return requested_id

    def _require_management(self) -> None:
        session = self._auth_service.require_authenticated()
        if not can_manage_attendance(session.role):
            raise PermissionError("You are not allowed to view employee attendance.")
