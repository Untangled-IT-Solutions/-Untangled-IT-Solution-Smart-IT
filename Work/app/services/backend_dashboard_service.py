"""Backend API dashboard service for the Windows desktop application.

The desktop client never connects to MongoDB directly. All dashboard metrics
come from the authenticated backend API.
"""
from __future__ import annotations

from typing import Any


class BackendDashboardService:
    """Fetch dashboard data through the authenticated backend API."""

    def __init__(self, backend_api) -> None:
        self._backend = backend_api

    def get_summary(self) -> dict[str, Any]:
        """Return a flat summary dict matching dashboard_view field names."""
        data = self._backend.request("GET", "/api/dashboard/summary")
        # Backend wraps metrics under "summary"
        if isinstance(data, dict) and isinstance(data.get("summary"), dict):
            summary = dict(data["summary"])
        else:
            summary = dict(data or {})

        # Ensure KPI keys always exist so the view never shows blanks.
        defaults = {
            "people_working": 0,
            "people_on_leave": 0,
            "people_on_site": 0,
            "tasks_due_today": 0,
            "tasks_overdue": 0,
            "tasks_waiting_review": 0,
            "completed_this_week": 0,
            "pending_approvals": 0,
            "pending_hr_reviews": 0,
            "sick_notes_pending": 0,
            "upcoming_deadlines": 0,
            "tasks_in_progress": 0,
            "pending_tasks": 0,
            "operations_inbox": 0,
            "total_employees": 0,
            "active_employees": 0,
            "workload": (),
            "active_assignments": (),
            "latest_activity": (),
        }
        for key, value in defaults.items():
            summary.setdefault(key, value)

        # Prefer quote "active" style counts for Active Work card when task
        # collections are empty on this backend deployment.
        if not summary.get("pending_tasks") and summary.get("total_quotes"):
            qbs = summary.get("quotes_by_status") or {}
            active_quotes = sum(
                int(qbs.get(k) or 0)
                for k in ("received", "assigned", "quoted", "approved", "payment")
            )
            summary["pending_tasks"] = active_quotes
            summary.setdefault("tasks_in_progress", int(qbs.get("assigned") or 0))

        return summary

    def get_business_lead_dashboard(self) -> dict[str, Any]:
        try:
            data = self._backend.request("GET", "/api/dashboard/business-lead")
            return data.get("summary") or data
        except Exception:
            # Fallback derived from main summary
            s = self.get_summary()
            return {
                "pending_approvals": s.get("pending_approvals", 0),
                "rfqs": 0,
                "supplier_registrations": 0,
                "technical_jobs": 0,
                "software_projects": 0,
                "operational_alerts": 0,
                "business_metrics": (
                    f"{s.get('pending_tasks', 0)} active items | "
                    f"{s.get('completed_this_week', 0)} completed this week"
                ),
            }

    def get_director_dashboard(self) -> dict[str, Any]:
        try:
            data = self._backend.request("GET", "/api/dashboard/director")
            return data.get("summary") or data
        except Exception:
            s = self.get_summary()
            working = s.get("people_working", 0)
            active = s.get("active_employees", 0)
            return {
                "executive_brief": "No executive briefs require attention.",
                "company_health": "Stable",
                "compliance": 0,
                "business_metrics": (
                    f"{s.get('pending_tasks', 0)} active items | "
                    f"{s.get('tasks_overdue', 0)} overdue"
                ),
                "inventory_alerts": 0,
                "upcoming_deadlines": s.get("upcoming_deadlines", 0),
                "attendance_summary": (
                    f"{working} of {active} active employees currently working"
                ),
                "financial_requests_waiting": 0,
            }
