"""Dashboard data service."""

import sqlite3
from pathlib import Path

from app.database.database import Database
from app.models.dashboard import BusinessLeadDashboard, DashboardSummary, DirectorDashboard
from app.models.notification import Activity


class DashboardService:
    """Calculates operational and executive dashboard values directly from SQLite."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def get_summary(self) -> DashboardSummary:
        """Return the current operational dashboard."""
        with self._connect() as connection:
            total_employees = self._count(connection, "SELECT COUNT(*) FROM employees;")
            active_employees = self._count(
                connection, "SELECT COUNT(*) FROM employees WHERE status = 'Active';"
            )
            people_working = self._count(
                connection,
                "SELECT COUNT(*) FROM employees WHERE status = 'Active' AND clocked_in = 1;",
            )
            people_on_leave = self._count(
                connection, "SELECT COUNT(*) FROM employees WHERE status = 'On Leave';"
            )
            people_on_site = self._count(
                connection,
                """
                SELECT COUNT(DISTINCT employees.id)
                FROM employees
                JOIN tasks ON tasks.assigned_employee = employees.full_name
                WHERE employees.clocked_in = 1
                AND tasks.category = 'Technical'
                AND tasks.status IN ('Assigned', 'In Progress', 'Waiting Review');
                """,
            )
            tasks_due_today = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE due_date = DATE('now', 'localtime')
                AND status NOT IN ('Completed', 'Cancelled');
                """,
            )
            tasks_overdue = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE due_date < DATE('now', 'localtime')
                AND due_date != ''
                AND status NOT IN ('Completed', 'Cancelled');
                """,
            )
            tasks_waiting_review = self._count(
                connection, "SELECT COUNT(*) FROM tasks WHERE status = 'Waiting Review';"
            )
            completed_this_week = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE status = 'Completed'
                AND DATE(COALESCE(updated_at, created_date, created_at))
                    >= DATE('now', 'localtime', '-6 days');
                """,
            )
            tasks_in_progress = self._count(
                connection, "SELECT COUNT(*) FROM tasks WHERE status = 'In Progress';"
            )
            pending_tasks = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE status IN ('New', 'Assigned', 'In Progress', 'Waiting Review');
                """,
            )
            pending_approvals = self._count(
                connection, "SELECT COUNT(*) FROM approvals WHERE status = 'Pending';"
            )
            upcoming_deadlines = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE due_date BETWEEN DATE('now', 'localtime')
                    AND DATE('now', 'localtime', '+7 days')
                AND status NOT IN ('Completed', 'Cancelled');
                """,
            ) + self._count(
                connection,
                """
                SELECT COUNT(*) FROM calendar_events
                WHERE start_date BETWEEN DATE('now', 'localtime')
                    AND DATE('now', 'localtime', '+7 days');
                """,
            )
            activity_rows = connection.execute(
                """
                SELECT * FROM activity_log
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 6;
                """
            ).fetchall()

        return DashboardSummary(
            people_working=people_working,
            people_on_leave=people_on_leave,
            people_on_site=people_on_site,
            tasks_due_today=tasks_due_today,
            tasks_overdue=tasks_overdue,
            tasks_waiting_review=tasks_waiting_review,
            completed_this_week=completed_this_week,
            pending_approvals=pending_approvals,
            upcoming_deadlines=upcoming_deadlines,
            latest_activity=tuple(self._row_to_activity(row) for row in activity_rows),
            total_employees=total_employees,
            active_employees=active_employees,
            tasks_in_progress=tasks_in_progress,
            pending_tasks=pending_tasks,
        )

    def get_business_lead_dashboard(self) -> BusinessLeadDashboard:
        """Return metrics relevant to the Business Lead."""
        with self._connect() as connection:
            pending_approvals = self._count(
                connection,
                """
                SELECT COUNT(*) FROM approvals
                WHERE status = 'Pending' AND current_stage = 'Business Lead';
                """,
            )
            rfqs = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE category IN ('RFQ', 'Tender')
                AND status NOT IN ('Completed', 'Cancelled');
                """,
            )
            supplier_registrations = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE category = 'Supplier Registration'
                AND status NOT IN ('Completed', 'Cancelled');
                """,
            )
            technical_jobs = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE category = 'Technical'
                AND status NOT IN ('Completed', 'Cancelled');
                """,
            )
            software_projects = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE category IN ('Software', 'Website')
                AND status NOT IN ('Completed', 'Cancelled');
                """,
            )
            operational_alerts = self._count(
                connection,
                """
                SELECT COUNT(*) FROM notifications
                WHERE is_read = 0 AND is_executive = 0;
                """,
            )
            active_work = self._count(
                connection,
                "SELECT COUNT(*) FROM tasks WHERE status NOT IN ('Completed', 'Cancelled');",
            )
            completed_week = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE status = 'Completed'
                AND DATE(COALESCE(updated_at, created_date, created_at))
                    >= DATE('now', 'localtime', '-6 days');
                """,
            )
        return BusinessLeadDashboard(
            pending_approvals=pending_approvals,
            rfqs=rfqs,
            supplier_registrations=supplier_registrations,
            technical_jobs=technical_jobs,
            software_projects=software_projects,
            operational_alerts=operational_alerts,
            business_metrics=f"{active_work} active work items | {completed_week} completed this week",
        )

    def get_director_dashboard(self) -> DirectorDashboard:
        """Return the Director's executive brief without operational notifications."""
        with self._connect() as connection:
            overdue = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE due_date < DATE('now', 'localtime')
                AND due_date != '' AND status NOT IN ('Completed', 'Cancelled');
                """,
            )
            compliance = self._count(
                connection,
                "SELECT COUNT(*) FROM notifications WHERE category = 'Compliance' AND is_read = 0;",
            )
            inventory_alerts = self._count(
                connection,
                "SELECT COUNT(*) FROM notifications WHERE category = 'Inventory' AND is_read = 0;",
            )
            upcoming = self._count(
                connection,
                """
                SELECT COUNT(*) FROM tasks
                WHERE due_date BETWEEN DATE('now', 'localtime')
                    AND DATE('now', 'localtime', '+7 days')
                AND status NOT IN ('Completed', 'Cancelled');
                """,
            )
            financial_requests_waiting = self._count(
                connection,
                """
                SELECT COUNT(*) FROM approvals
                WHERE status = 'Pending'
                AND request_type IN ('Equipment', 'Software', 'Purchases', 'Budget');
                """,
            )
            total_employees = self._count(connection, "SELECT COUNT(*) FROM employees WHERE status = 'Active';")
            working = self._count(
                connection, "SELECT COUNT(*) FROM employees WHERE status = 'Active' AND clocked_in = 1;"
            )
            active_work = self._count(
                connection, "SELECT COUNT(*) FROM tasks WHERE status NOT IN ('Completed', 'Cancelled');"
            )
            brief_row = connection.execute(
                """
                SELECT message FROM notifications
                WHERE recipient_role = 'Director' AND is_executive = 1
                ORDER BY datetime(created_at) DESC, id DESC LIMIT 1;
                """
            ).fetchone()
        brief = brief_row["message"] if brief_row is not None else "No executive briefs require attention."
        health = "Attention required" if overdue or compliance else "Stable"
        return DirectorDashboard(
            executive_brief=brief,
            company_health=health,
            compliance=compliance,
            business_metrics=f"{active_work} active work items | {overdue} overdue",
            inventory_alerts=inventory_alerts,
            upcoming_deadlines=upcoming,
            attendance_summary=f"{working} of {total_employees} active employees currently working",
            financial_requests_waiting=financial_requests_waiting,
        )

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    @staticmethod
    def _count(connection: sqlite3.Connection, query: str) -> int:
        return int(connection.execute(query).fetchone()[0])

    @staticmethod
    def _row_to_activity(row: sqlite3.Row) -> Activity:
        return Activity(
            id=row["id"],
            category=row["category"],
            description=row["description"],
            reference_type=row["reference_type"] or "",
            reference_id=row["reference_id"],
            created_at=row["created_at"],
        )
