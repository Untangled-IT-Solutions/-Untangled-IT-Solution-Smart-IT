"""Backend-only service layer."""

from app.services.backend_api_client import BackendAPIClient, BackendAPIError
from app.services.auth_service import AuthService
from app.services.backend_auth_service import BackendAuthService
from app.services.mongo_attendance_service import MongoAttendanceService
from app.services.attendance_service import AttendanceService
from app.services.people_service import PeopleService
from app.services.dashboard_service import DashboardService
from app.services.work_service import WorkService
from app.services.approval_service import ApprovalService
from app.services.calendar_service import CalendarService
from app.services.office_request_service import OfficeRequestService
from app.services.project_service import ProjectService
from app.services.report_service import ReportService
from app.services.notification_service import NotificationService, MongoNotificationService

__all__ = [
    "BackendAPIClient",
    "BackendAPIError",
    "AuthService",
    "BackendAuthService",
    "MongoAttendanceService",
    "AttendanceService",
    "PeopleService",
    "DashboardService",
    "WorkService",
    "ApprovalService",
    "CalendarService",
    "OfficeRequestService",
    "ProjectService",
    "ReportService",
    "NotificationService",
    "MongoNotificationService",
]
