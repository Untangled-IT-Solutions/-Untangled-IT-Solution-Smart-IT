"""Dashboard controller."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.auth_service import AuthService

from app.models.dashboard import BusinessLeadDashboard, DashboardSummary, DirectorDashboard
from app.services.attendance_service import AttendanceService
from app.services.dashboard_service import DashboardService
from app.services.notification_service import NotificationService
from app.services.work_service import WorkService


class DashboardController:
    """Provides dashboard data to views."""

    def __init__(
        self,
        dashboard_service: DashboardService,
        auth_service,  # AuthService
        attendance_service: AttendanceService,
        work_service: WorkService,
        notification_service: NotificationService,
    ) -> None:
        self._dashboard_service = dashboard_service
        self._auth_service = auth_service
        self._attendance_service = attendance_service
        self._work_service = work_service
        self._notification_service = notification_service

    def get_summary(self) -> DashboardSummary:
        """Return the current dashboard summary."""
        return self._dashboard_service.get_summary()

    def get_business_lead_dashboard(self) -> BusinessLeadDashboard:
        return self._dashboard_service.get_business_lead_dashboard()

    def get_director_dashboard(self) -> DirectorDashboard:
        return self._dashboard_service.get_director_dashboard()

    def get_identity_summary(self) -> dict[str, str]:
        session = self._auth_service.require_authenticated()
        record = self._attendance_service.get_today_record(session.employee_id)
        status = "Not clocked in"
        today_hours = "0.00"
        if record is not None:
            status = "On break" if record.is_on_break else ("Clocked in" if record.is_clocked_in else "Clocked out")
            today_hours = f"{self._attendance_service.get_live_hours(record):.2f}"
        pending_work = len([
            task for task in self._work_service.get_all_work(assigned_employee=session.account.full_name)
            if task.status not in {"Completed", "Cancelled"}
        ])
        unread = len(self._notification_service.get_notifications(session.role, unread_only=True))
        return {
            "user": session.account.full_name,
            "role": session.role,
            "clock_status": status,
            "today_hours": today_hours,
            "pending_work": str(pending_work),
            "unread_notifications": str(unread),
        }

