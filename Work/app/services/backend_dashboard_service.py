"""Backend API dashboard service for the Windows desktop application.

The desktop client never connects to MongoDB directly. All dashboard metrics
come from the authenticated backend API.
"""
from __future__ import annotations

from typing import Any


class BackendDashboardService:
    """Fetch dashboard data through the authenticated backend API."""

    def __init__(self, backend_api: Any) -> None:
        self._backend = backend_api

    def get_summary(self) -> dict[str, Any]:
        """Return a flat summary dict matching dashboard_view field names."""
        try:
            data = self._backend.request("GET", "/api/dashboard/summary")
        except Exception as exc:
            print(f"[dashboard] Backend /api/dashboard/summary failed: {exc}")
            return {
                "people_working": 0,
                "people_on_leave": 0,
                "people_on_site": 0,
                "tasks_due_today": 0,
                "tasks_overdue": 0,
                "tasks_waiting_review": 0,
                "completed_this_week": 0,
                "pending_approvals": 0,
                "upcoming_deadlines": 0,
                "tasks_in_progress": 0,
                "pending_tasks": 0,
                "total_employees": 0,
                "active_employees": 0,
                "latest_activity": (),
                "error": str(exc),
            }

        if isinstance(data, dict) and isinstance(data.get("summary"), dict):
            summary = dict(data["summary"])
        else:
            summary = dict(data or {})

        # Coerce people_working strictly from API; never invent from local state
        try:
            summary["people_working"] = int(summary.get("people_working") or 0)
        except (TypeError, ValueError):
            summary["people_working"] = 0

        summary["people_on_site"] = summary["people_working"]

        defaults = {
            "people_working": 0,
            "people_on_leave": 0,
            "people_on_site": 0,
            "tasks_due_today": 0,
            "tasks_overdue": 0,
            "tasks_waiting_review": 0,
            "completed_this_week": 0,
            "pending_approvals": 0,
            "upcoming_deadlines": 0,
            "tasks_in_progress": 0,
            "pending_tasks": 0,
            "total_employees": 0,
            "active_employees": 0,
            "latest_activity": (),
        }
        for key, value in defaults.items():
            summary.setdefault(key, value)

        if not summary.get("pending_tasks") and summary.get("total_quotes"):
            qbs = summary.get("quotes_by_status") or {}
            active_quotes = sum(
                int(qbs.get(k) or 0)
                for k in ("received", "assigned", "quoted", "approved", "payment")
            )
            summary["pending_tasks"] = active_quotes
            summary.setdefault("tasks_in_progress", int(qbs.get("assigned") or 0))

        print(
            f"[dashboard] people_working={summary.get('people_working')} "
            f"work_date={summary.get('_debug_work_date')} "
            f"open_docs={summary.get('_debug_open_attendance_docs')}"
        )
        return summary

    def get_business_lead_dashboard(self) -> dict[str, Any]:
        try:
            data = self._backend.request("GET", "/api/dashboard/business-lead")
            return data.get("summary") or data
        except Exception:
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
