"""Dashboard view models."""

from dataclasses import dataclass

from app.models.notification import Activity


@dataclass(frozen=True)
class DashboardSummary:
    """Operational summary values shown on the main dashboard."""

    people_working: int
    people_on_leave: int
    people_on_site: int
    tasks_due_today: int
    tasks_overdue: int
    tasks_waiting_review: int
    completed_this_week: int
    pending_approvals: int
    upcoming_deadlines: int
    latest_activity: tuple[Activity, ...]
    total_employees: int
    active_employees: int
    tasks_in_progress: int
    pending_tasks: int

    @property
    def employees(self) -> int:
        """Compatibility alias for the first dashboard release."""
        return self.total_employees


@dataclass(frozen=True)
class BusinessLeadDashboard:
    """Business-lead operational and approval view model."""

    pending_approvals: int
    rfqs: int
    supplier_registrations: int
    technical_jobs: int
    software_projects: int
    operational_alerts: int
    business_metrics: str


@dataclass(frozen=True)
class DirectorDashboard:
    """Executive-only dashboard view model."""

    executive_brief: str
    company_health: str
    compliance: int
    business_metrics: str
    inventory_alerts: int
    upcoming_deadlines: int
    attendance_summary: str
    financial_requests_waiting: int
