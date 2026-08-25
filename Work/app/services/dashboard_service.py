"""MongoDB-backed dashboard data service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.models.dashboard import (
    BusinessLeadDashboard,
    DashboardSummary,
    DirectorDashboard,
)
from app.models.notification import Activity
from app.services.mongodb_service import MongoDBService


class DashboardService:
    """Calculates dashboard values directly from MongoDB."""

    ACTIVE_TASK_STATUSES = {
        "New",
        "Assigned",
        "In Progress",
        "Waiting Review",
    }

    CLOSED_TASK_STATUSES = {
        "Completed",
        "Cancelled",
    }

    def __init__(self, database: MongoDBService) -> None:
        self._database = database

    # ==================================================================
    # GENERAL HELPERS
    # ==================================================================

    @property
    def db(self) -> Any:
        return self._database.db

    @property
    def employees(self) -> Any:
        return self.db["employees"]

    @property
    def tasks(self) -> Any:
        return self.db["work_assignments"]

    @property
    def approvals(self) -> Any:
        return self.db["approvals"]

    @property
    def notifications(self) -> Any:
        return self.db["notifications"]

    @property
    def activity(self) -> Any:
        """
        MongoDB collection containing operational activity.

        If your application uses another collection name, change it here.
        """
        return self.db["activity_log"]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _start_of_today() -> datetime:
        now = datetime.now(timezone.utc)

        return now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _end_of_today() -> datetime:
        return DashboardService._start_of_today() + timedelta(days=1)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    # ==================================================================
    # DATE HELPERS
    # ==================================================================

    @staticmethod
    def _date_range_for_today() -> Dict[str, Any]:
        start = DashboardService._start_of_today()
        end = DashboardService._end_of_today()

        return {
            "$gte": start,
            "$lt": end,
        }

    @staticmethod
    def _date_value_filter(
        field: str,
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:
        return {
            field: {
                "$gte": start,
                "$lt": end,
            }
        }

    # ==================================================================
    # TASK HELPERS
    # ==================================================================

    def _task_count(
        self,
        query: Dict[str, Any] | None = None,
    ) -> int:
        return self._safe_int(
            self.tasks.count_documents(query or {})
        )

    def _active_task_query(self) -> Dict[str, Any]:
        return {
            "status": {
                "$nin": list(self.CLOSED_TASK_STATUSES)
            }
        }

    # ==================================================================
    # SUMMARY
    # ==================================================================

    def get_summary(self) -> DashboardSummary:
        """Return the current operational dashboard."""

        now = self._now()
        today_start = self._start_of_today()
        tomorrow = self._end_of_today()
        seven_days = today_start + timedelta(days=7)
        week_start = today_start - timedelta(days=6)

        # --------------------------------------------------------------
        # EMPLOYEES
        # --------------------------------------------------------------

        total_employees = self._safe_int(
            self.employees.count_documents({})
        )

        active_employees = self._safe_int(
            self.employees.count_documents(
                {
                    "status": "Active",
                }
            )
        )

        people_working = self._safe_int(
            self.employees.count_documents(
                {
                    "status": "Active",
                    "clocked_in": True,
                }
            )
        )

        people_on_leave = self._safe_int(
            self.employees.count_documents(
                {
                    "status": "On Leave",
                }
            )
        )

        # --------------------------------------------------------------
        # PEOPLE ON SITE
        # --------------------------------------------------------------

        people_on_site = self._safe_int(
            self.tasks.count_documents(
                {
                    "category": "Technical",
                    "status": {
                        "$in": [
                            "Assigned",
                            "In Progress",
                            "Waiting Review",
                        ]
                    },
                    "employee_id": {
                        "$exists": True,
                        "$ne": None,
                    },
                }
            )
        )

        # If your work_assignments documents contain duplicate
        # assignments for the same employee, use aggregation instead.
        # See the note below.

        # --------------------------------------------------------------
        # TASKS DUE TODAY
        # --------------------------------------------------------------

        tasks_due_today = self._safe_int(
            self.tasks.count_documents(
                {
                    "due_date": {
                        "$gte": today_start,
                        "$lt": tomorrow,
                    },
                    "status": {
                        "$nin": list(
                            self.CLOSED_TASK_STATUSES
                        )
                    },
                }
            )
        )

        # --------------------------------------------------------------
        # OVERDUE
        # --------------------------------------------------------------

        tasks_overdue = self._safe_int(
            self.tasks.count_documents(
                {
                    "due_date": {
                        "$lt": now,
                    },
                    "status": {
                        "$nin": list(
                            self.CLOSED_TASK_STATUSES
                        )
                    },
                }
            )
        )

        # --------------------------------------------------------------
        # WAITING REVIEW
        # --------------------------------------------------------------

        tasks_waiting_review = self._safe_int(
            self.tasks.count_documents(
                {
                    "status": "Waiting Review",
                }
            )
        )

        # --------------------------------------------------------------
        # COMPLETED THIS WEEK
        # --------------------------------------------------------------

        completed_this_week = self._safe_int(
            self.tasks.count_documents(
                {
                    "status": "Completed",
                    "$or": [
                        {
                            "updated_at": {
                                "$gte": week_start,
                            }
                        },
                        {
                            "updatedAt": {
                                "$gte": week_start,
                            }
                        },
                    ],
                }
            )
        )

        # --------------------------------------------------------------
        # IN PROGRESS
        # --------------------------------------------------------------

        tasks_in_progress = self._safe_int(
            self.tasks.count_documents(
                {
                    "status": "In Progress",
                }
            )
        )

        # --------------------------------------------------------------
        # PENDING TASKS
        # --------------------------------------------------------------

        pending_tasks = self._safe_int(
            self.tasks.count_documents(
                {
                    "status": {
                        "$in": list(
                            self.ACTIVE_TASK_STATUSES
                        )
                    }
                }
            )
        )

        # --------------------------------------------------------------
        # APPROVALS
        # --------------------------------------------------------------

        pending_approvals = self._safe_int(
            self.approvals.count_documents(
                {
                    "status": "Pending",
                }
            )
        )

        # --------------------------------------------------------------
        # UPCOMING DEADLINES
        # --------------------------------------------------------------

        upcoming_task_deadlines = self._safe_int(
            self.tasks.count_documents(
                {
                    "due_date": {
                        "$gte": today_start,
                        "$lt": seven_days,
                    },
                    "status": {
                        "$nin": list(
                            self.CLOSED_TASK_STATUSES
                        )
                    },
                }
            )
        )

        upcoming_events = 0

        if "calendar_events" in self.db.list_collection_names():
            upcoming_events = self._safe_int(
                self.db["calendar_events"].count_documents(
                    {
                        "start_date": {
                            "$gte": today_start,
                            "$lt": seven_days,
                        }
                    }
                )
            )

        upcoming_deadlines = (
            upcoming_task_deadlines
            + upcoming_events
        )

        # --------------------------------------------------------------
        # ACTIVITY
        # --------------------------------------------------------------

        activity_rows = list(
            self.activity.find({})
            .sort(
                [
                    ("created_at", -1),
                    ("createdAt", -1),
                    ("_id", -1),
                ]
            )
            .limit(6)
        )

        latest_activity = tuple(
            self._row_to_activity(row)
            for row in activity_rows
        )

        # --------------------------------------------------------------
        # RETURN MODEL
        # --------------------------------------------------------------

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
            latest_activity=latest_activity,
            total_employees=total_employees,
            active_employees=active_employees,
            tasks_in_progress=tasks_in_progress,
            pending_tasks=pending_tasks,
        )

    # ==================================================================
    # BUSINESS LEAD
    # ==================================================================

    def get_business_lead_dashboard(
        self,
    ) -> BusinessLeadDashboard:
        """Return metrics relevant to the Business Lead."""

        pending_approvals = self._safe_int(
            self.approvals.count_documents(
                {
                    "status": "Pending",
                    "current_stage": "Business Lead",
                }
            )
        )

        rfqs = self._task_count(
            {
                "category": {
                    "$in": [
                        "RFQ",
                        "Tender",
                    ]
                },
                "status": {
                    "$nin": list(
                        self.CLOSED_TASK_STATUSES
                    )
                },
            }
        )

        supplier_registrations = self._task_count(
            {
                "category": "Supplier Registration",
                "status": {
                    "$nin": list(
                        self.CLOSED_TASK_STATUSES
                    )
                },
            }
        )

        technical_jobs = self._task_count(
            {
                "category": "Technical",
                "status": {
                    "$nin": list(
                        self.CLOSED_TASK_STATUSES
                    )
                },
            }
        )

        software_projects = self._task_count(
            {
                "category": {
                    "$in": [
                        "Software",
                        "Website",
                    ]
                },
                "status": {
                    "$nin": list(
                        self.CLOSED_TASK_STATUSES
                    )
                },
            }
        )

        operational_alerts = self._safe_int(
            self.notifications.count_documents(
                {
                    "is_read": False,
                    "is_executive": False,
                }
            )
        )

        active_work = self._task_count(
            self._active_task_query()
        )

        week_start = self._start_of_today() - timedelta(days=6)

        completed_week = self._safe_int(
            self.tasks.count_documents(
                {
                    "status": "Completed",
                    "$or": [
                        {
                            "updated_at": {
                                "$gte": week_start,
                            }
                        },
                        {
                            "updatedAt": {
                                "$gte": week_start,
                            }
                        },
                    ],
                }
            )
        )

        return BusinessLeadDashboard(
            pending_approvals=pending_approvals,
            rfqs=rfqs,
            supplier_registrations=supplier_registrations,
            technical_jobs=technical_jobs,
            software_projects=software_projects,
            operational_alerts=operational_alerts,
            business_metrics=(
                f"{active_work} active work items | "
                f"{completed_week} completed this week"
            ),
        )

    # ==================================================================
    # DIRECTOR
    # ==================================================================

    def get_director_dashboard(
        self,
    ) -> DirectorDashboard:
        """Return the Director's executive dashboard."""

        now = self._now()
        today_start = self._start_of_today()
        seven_days = today_start + timedelta(days=7)

        overdue = self._task_count(
            {
                "due_date": {
                    "$lt": now,
                },
                "status": {
                    "$nin": list(
                        self.CLOSED_TASK_STATUSES
                    )
                },
            }
        )

        compliance = self._safe_int(
            self.notifications.count_documents(
                {
                    "category": "Compliance",
                    "is_read": False,
                }
            )
        )

        inventory_alerts = self._safe_int(
            self.notifications.count_documents(
                {
                    "category": "Inventory",
                    "is_read": False,
                }
            )
        )

        upcoming = self._task_count(
            {
                "due_date": {
                    "$gte": today_start,
                    "$lt": seven_days,
                },
                "status": {
                    "$nin": list(
                        self.CLOSED_TASK_STATUSES
                    )
                },
            }
        )

        financial_requests_waiting = self._safe_int(
            self.approvals.count_documents(
                {
                    "status": "Pending",
                    "request_type": {
                        "$in": [
                            "Equipment",
                            "Software",
                            "Purchases",
                            "Budget",
                        ]
                    },
                }
            )
        )

        total_employees = self._safe_int(
            self.employees.count_documents(
                {
                    "status": "Active",
                }
            )
        )

        working = self._safe_int(
            self.employees.count_documents(
                {
                    "status": "Active",
                    "clocked_in": True,
                }
            )
        )

        active_work = self._task_count(
            self._active_task_query()
        )

        brief_row = self.notifications.find_one(
            {
                "recipient_role": "Director",
                "is_executive": True,
            },
            sort=[
                ("created_at", -1),
                ("createdAt", -1),
                ("_id", -1),
            ],
        )

        if brief_row:
            brief = (
                brief_row.get("message")
                or "No executive briefs require attention."
            )
        else:
            brief = (
                "No executive briefs require attention."
            )

        health = (
            "Attention required"
            if overdue or compliance
            else "Stable"
        )

        return DirectorDashboard(
            executive_brief=brief,
            company_health=health,
            compliance=compliance,
            business_metrics=(
                f"{active_work} active work items | "
                f"{overdue} overdue"
            ),
            inventory_alerts=inventory_alerts,
            upcoming_deadlines=upcoming,
            attendance_summary=(
                f"{working} of {total_employees} "
                "active employees currently working"
            ),
            financial_requests_waiting=(
                financial_requests_waiting
            ),
        )

    # ==================================================================
    # ACTIVITY CONVERSION
    # ==================================================================

    @staticmethod
    def _row_to_activity(
        row: Dict[str, Any],
    ) -> Activity:
        """Convert a MongoDB activity document into Activity."""

        created_at = (
            row.get("created_at")
            or row.get("createdAt")
        )

        return Activity(
            id=str(
                row.get("id")
                or row.get("_id")
                or ""
            ),
            category=str(
                row.get("category")
                or "Activity"
            ),
            description=str(
                row.get("description")
                or row.get("message")
                or ""
            ),
            reference_type=str(
                row.get("reference_type")
                or row.get("referenceType")
                or ""
            ),
            reference_id=row.get(
                "reference_id",
                row.get("referenceId"),
            ),
            created_at=created_at,
        )