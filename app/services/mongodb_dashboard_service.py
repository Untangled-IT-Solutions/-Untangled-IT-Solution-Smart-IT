"""MongoDB-backed dashboard data service.

The dashboard is intentionally read-only and data-driven.

IMPORTANT:
    - No demo numbers.
    - No SQLite queries.
    - No test-database fallback.
    - Dashboard counts come only from the configured MongoDB database.
    - Active work is counted once.
    - People Working means employees with a currently open attendance record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pymongo import DESCENDING


@dataclass(frozen=True)
class DashboardActivity:
    """Small dashboard activity object compatible with the dashboard view."""

    id: Any
    category: str
    description: str
    reference_type: str = ""
    reference_id: Any = None
    created_at: Any = None


@dataclass(frozen=True)
class DashboardSummary:
    """Live operational dashboard summary."""

    people_working: int
    people_on_leave: int
    people_on_site: int

    tasks_due_today: int
    tasks_overdue: int
    tasks_waiting_review: int
    completed_this_week: int

    pending_approvals: int
    upcoming_deadlines: int

    latest_activity: tuple[DashboardActivity, ...]

    total_employees: int
    active_employees: int

    tasks_in_progress: int
    pending_tasks: int

    # Additional real MongoDB metrics.
    total_work_assignments: int
    active_work_assignments: int

    total_quotes: int
    active_quotes: int

    total_orders: int
    active_orders: int


@dataclass(frozen=True)
class BusinessLeadDashboard:
    """Business Lead dashboard."""

    pending_approvals: int
    rfqs: int
    supplier_registrations: int
    technical_jobs: int
    software_projects: int
    operational_alerts: int
    business_metrics: str


@dataclass(frozen=True)
class DirectorDashboard:
    """Director dashboard."""

    executive_brief: str
    company_health: str
    compliance: int
    business_metrics: str
    inventory_alerts: int
    upcoming_deadlines: int
    attendance_summary: str
    financial_requests_waiting: int


class MongoDBDashboardService:
    """Calculates dashboard values directly from the configured MongoDB database."""

    COMPLETED_STATUSES = {
        "Completed",
        "complete",
        "completed",
        "Closed",
        "closed",
        "Done",
        "done",
    }

    CANCELLED_STATUSES = {
        "Cancelled",
        "Canceled",
        "cancelled",
        "canceled",
    }

    ACTIVE_EMPLOYEE_STATUSES = {
        "Active",
        "active",
    }

    LEAVE_EMPLOYEE_STATUSES = {
        "On Leave",
        "on leave",
        "Leave",
        "leave",
    }

    IN_PROGRESS_STATUSES = {
        "In Progress",
        "in progress",
        "InProgress",
        "in_progress",
    }

    WAITING_REVIEW_STATUSES = {
        "Waiting Review",
        "waiting review",
        "Waiting for Review",
        "waiting_for_review",
    }

    OPEN_ASSIGNMENT_STATUSES = {
        "New",
        "new",
        "Assigned",
        "assigned",
        "In Progress",
        "in progress",
        "InProgress",
        "in_progress",
        "Waiting Review",
        "waiting review",
        "Waiting for Review",
        "waiting_for_review",
    }

    ACTIVE_ORDER_STATUSES = {
        "New",
        "new",
        "Pending",
        "pending",
        "Processing",
        "processing",
        "Confirmed",
        "confirmed",
        "In Progress",
        "in progress",
        "Assigned",
        "assigned",
        "Open",
        "open",
    }

    ACTIVE_QUOTE_STATUSES = {
        "Draft",
        "draft",
        "Pending",
        "pending",
        "Sent",
        "sent",
        "Quoted",
        "quoted",
        "Open",
        "open",
        "Awaiting Response",
        "awaiting response",
    }

    def __init__(self, mongodb_service) -> None:
        """Create the dashboard service using the existing MongoDB service."""
        self._mongo = mongodb_service

    # ==================================================================
    # DATABASE
    # ==================================================================

    @property
    def db(self):
        """Return the configured application database only."""
        return self._mongo.db

    @property
    def database_name(self) -> str:
        """Return the configured MongoDB database name."""
        return getattr(
            self._mongo,
            "_db_name",
            "configured database",
        )

    def _collection(self, name: str):
        """Return a collection from the configured database."""
        return self._mongo.get_collection(name)

    # ==================================================================
    # DATE / TIME
    # ==================================================================

    @staticmethod
    def _now() -> datetime:
        """Return current UTC time."""
        return datetime.now(timezone.utc)

    @classmethod
    def _start_of_today(cls) -> datetime:
        """Return today's UTC midnight."""
        now = cls._now()
        return datetime(
            now.year,
            now.month,
            now.day,
            tzinfo=timezone.utc,
        )

    @classmethod
    def _end_of_today(cls) -> datetime:
        """Return the start of tomorrow."""
        return cls._start_of_today() + timedelta(days=1)

    @classmethod
    def _start_of_week(cls) -> datetime:
        """Return the start of the current Monday."""
        today = cls._start_of_today()
        return today - timedelta(days=today.weekday())

    @staticmethod
    def _date_variants(value: datetime) -> list[Any]:
        """
        Return common date representations used by existing Mongo documents.

        Existing records may contain:
            datetime
            ISO string
            YYYY-MM-DD
        """
        return [
            value,
            value.isoformat(),
            value.date().isoformat(),
        ]

    # ==================================================================
    # GENERAL HELPERS
    # ==================================================================

    @staticmethod
    def _count(collection, query: Optional[dict[str, Any]] = None) -> int:
        """Safely count documents."""
        try:
            return int(
                collection.count_documents(
                    query or {},
                )
            )
        except Exception as exc:
            print(
                f"⚠️ Dashboard count failed for "
                f"{collection.name}: {exc}"
            )
            return 0

    @staticmethod
    def _status_not_completed_cancelled() -> dict[str, Any]:
        """Mongo filter for records which are not finished/cancelled."""
        return {
            "$nin": list(
                MongoDBDashboardService.COMPLETED_STATUSES
                | MongoDBDashboardService.CANCELLED_STATUSES
            )
        }

    @staticmethod
    def _first_existing(document: dict[str, Any], *names: str) -> Any:
        """Return the first existing non-null document field."""
        for name in names:
            if name in document and document[name] is not None:
                return document[name]
        return None

    @classmethod
    def _status(cls, document: dict[str, Any]) -> str:
        """Extract a normalized status."""
        value = cls._first_existing(
            document,
            "status",
            "state",
        )

        if value is None:
            return ""

        return str(value).strip()

    @classmethod
    def _is_completed(cls, document: dict[str, Any]) -> bool:
        return cls._status(document) in cls.COMPLETED_STATUSES

    @classmethod
    def _is_cancelled(cls, document: dict[str, Any]) -> bool:
        return cls._status(document) in cls.CANCELLED_STATUSES

    # ==================================================================
    # ATTENDANCE
    # ==================================================================

    def _people_working(self) -> int:
        """
        Count employees who are actually clocked in.

        Attendance is the source of truth.

        A current attendance document is active when:
            clock_in_at exists
            AND clock_out_at does not exist / is null / is empty.
        """
        attendance = self._collection("attendance")

        today = self._start_of_today()

        queries = [
            {
                "work_date": {
                    "$in": self._date_variants(today),
                },
                "clock_in_at": {
                    "$exists": True,
                    "$ne": None,
                    "$ne": "",
                },
                "$or": [
                    {
                        "clock_out_at": {
                            "$exists": False,
                        }
                    },
                    {
                        "clock_out_at": None,
                    },
                    {
                        "clock_out_at": "",
                    },
                ],
            },
        ]

        try:
            for query in queries:
                return self._count(
                    attendance,
                    query,
                )
        except Exception:
            pass

        return 0

    def _people_working_from_employee_state(self) -> int:
        """
        Fallback only when attendance documents don't expose the expected
        clock-in fields.

        This uses the employee's persisted clocked-in flag.
        """
        employees = self._collection("employees")

        return self._count(
            employees,
            {
                "status": {
                    "$in": list(
                        self.ACTIVE_EMPLOYEE_STATUSES
                    )
                },
                "clocked_in": True,
            },
        )

    def _get_people_working(self) -> int:
        """Get current working count without counting registered users."""
        count = self._people_working()

        if count > 0:
            return count

        # If nobody is currently working, verify whether employee state
        # explicitly reports somebody clocked in.
        return self._people_working_from_employee_state()

    # ==================================================================
    # EMPLOYEES
    # ==================================================================

    def _employee_counts(self) -> tuple[int, int, int]:
        """Return total, active and on-leave employee counts."""
        employees = self._collection("employees")

        total = self._count(employees)

        active = self._count(
            employees,
            {
                "status": {
                    "$in": list(
                        self.ACTIVE_EMPLOYEE_STATUSES
                    )
                }
            },
        )

        on_leave = self._count(
            employees,
            {
                "status": {
                    "$in": list(
                        self.LEAVE_EMPLOYEE_STATUSES
                    )
                }
            },
        )

        return total, active, on_leave

    # ==================================================================
    # WORK ASSIGNMENTS
    # ==================================================================

    def _work_assignment_filter_active(self) -> dict[str, Any]:
        """Return the canonical open-work filter."""
        return {
            "status": {
                "$nin": list(
                    self.COMPLETED_STATUSES
                    | self.CANCELLED_STATUSES
                )
            }
        }

    def _work_assignment_counts(self) -> tuple[int, int, int, int]:
        """
        Return:

            total assignments
            active assignments
            in-progress assignments
            waiting-review assignments
        """
        collection = self._collection("work_assignments")

        total = self._count(collection)

        active = self._count(
            collection,
            self._work_assignment_filter_active(),
        )

        in_progress = self._count(
            collection,
            {
                "status": {
                    "$in": list(
                        self.IN_PROGRESS_STATUSES
                    )
                }
            },
        )

        waiting_review = self._count(
            collection,
            {
                "status": {
                    "$in": list(
                        self.WAITING_REVIEW_STATUSES
                    )
                }
            },
        )

        return (
            total,
            active,
            in_progress,
            waiting_review,
        )

    def _tasks_due_today(self) -> int:
        """Count active work assignments due today."""
        collection = self._collection("work_assignments")

        start = self._start_of_today()
        end = self._end_of_today()

        return self._count(
            collection,
            {
                "$and": [
                    {
                        "$or": [
                            {
                                "due_date": {
                                    "$gte": start,
                                    "$lt": end,
                                }
                            },
                            {
                                "dueDate": {
                                    "$gte": start,
                                    "$lt": end,
                                }
                            },
                            {
                                "due_date": {
                                    "$in": self._date_variants(start),
                                }
                            },
                            {
                                "dueDate": {
                                    "$in": self._date_variants(start),
                                }
                            },
                        ]
                    },
                    self._work_assignment_filter_active(),
                ]
            },
        )

    def _tasks_overdue(self) -> int:
        """Count active work assignments whose due date has passed."""
        collection = self._collection("work_assignments")

        now = self._now()

        return self._count(
            collection,
            {
                "$and": [
                    {
                        "$or": [
                            {
                                "due_date": {
                                    "$lt": now,
                                }
                            },
                            {
                                "dueDate": {
                                    "$lt": now,
                                }
                            },
                        ]
                    },
                    self._work_assignment_filter_active(),
                ]
            },
        )

    def _completed_this_week(self) -> int:
        """Count work completed since the start of this week."""
        collection = self._collection("work_assignments")

        start = self._start_of_week()

        return self._count(
            collection,
            {
                "status": {
                    "$in": list(
                        self.COMPLETED_STATUSES
                    )
                },
                "$or": [
                    {
                        "updated_at": {
                            "$gte": start,
                        }
                    },
                    {
                        "updatedAt": {
                            "$gte": start,
                        }
                    },
                    {
                        "completed_at": {
                            "$gte": start,
                        }
                    },
                    {
                        "completedAt": {
                            "$gte": start,
                        }
                    },
                ],
            },
        )

    # ==================================================================
    # QUOTES
    # ==================================================================

    def _quote_counts(self) -> tuple[int, int]:
        """
        Return total and active quotes.

        IMPORTANT:
            Only the configured application database is queried.
            There is NO test database fallback.
        """
        quotes = self._collection("quotes")

        total = self._count(quotes)

        active = self._count(
            quotes,
            {
                "status": {
                    "$in": list(
                        self.ACTIVE_QUOTE_STATUSES
                    )
                }
            },
        )

        return total, active

    # ==================================================================
    # ORDERS
    # ==================================================================

    def _order_counts(self) -> tuple[int, int]:
        """
        Return total and active orders.

        IMPORTANT:
            Only the configured application database is queried.
            There is NO test database fallback.
        """
        orders = self._collection("orders")

        total = self._count(orders)

        active = self._count(
            orders,
            {
                "status": {
                    "$in": list(
                        self.ACTIVE_ORDER_STATUSES
                    )
                }
            },
        )

        return total, active

    # ==================================================================
    # APPROVALS
    # ==================================================================

    def _pending_approvals(self) -> int:
        """Count pending approvals."""
        return self._count(
            self._collection("approvals"),
            {
                "status": {
                    "$in": [
                        "Pending",
                        "pending",
                    ]
                }
            },
        )

    # ==================================================================
    # UPCOMING DEADLINES
    # ==================================================================

    def _upcoming_deadlines(self) -> int:
        """Count active work assignments due within the next seven days."""
        collection = self._collection("work_assignments")

        start = self._start_of_today()
        end = start + timedelta(days=7)

        return self._count(
            collection,
            {
                "$and": [
                    {
                        "$or": [
                            {
                                "due_date": {
                                    "$gte": start,
                                    "$lt": end,
                                }
                            },
                            {
                                "dueDate": {
                                    "$gte": start,
                                    "$lt": end,
                                }
                            },
                        ]
                    },
                    self._work_assignment_filter_active(),
                ]
            },
        )

    # ==================================================================
    # ACTIVITY
    # ==================================================================

    def _latest_activity(
        self,
        limit: int = 6,
    ) -> tuple[DashboardActivity, ...]:
        """
        Read recent operational activity.

        Supports common Mongo activity collection names.
        """
        collection_names = self.db.list_collection_names()

        preferred = [
            "activity_log",
            "activities",
            "activity",
            "daily_activities",
        ]

        collection_name = next(
            (
                name
                for name in preferred
                if name in collection_names
            ),
            None,
        )

        if collection_name is None:
            return ()

        collection = self._collection(collection_name)

        try:
            rows = list(
                collection.find()
                .sort(
                    [
                        ("created_at", DESCENDING),
                        ("createdAt", DESCENDING),
                        ("date", DESCENDING),
                    ]
                )
                .limit(limit)
            )
        except Exception:
            try:
                rows = list(
                    collection.find()
                    .sort("createdAt", DESCENDING)
                    .limit(limit)
                )
            except Exception:
                return ()

        result: list[DashboardActivity] = []

        for row in rows:
            result.append(
                DashboardActivity(
                    id=row.get("_id"),
                    category=str(
                        self._first_existing(
                            row,
                            "category",
                            "type",
                            "event_type",
                        )
                        or "Activity"
                    ),
                    description=str(
                        self._first_existing(
                            row,
                            "description",
                            "message",
                            "activity",
                        )
                        or ""
                    ),
                    reference_type=str(
                        self._first_existing(
                            row,
                            "reference_type",
                            "referenceType",
                        )
                        or ""
                    ),
                    reference_id=self._first_existing(
                        row,
                        "reference_id",
                        "referenceId",
                    ),
                    created_at=self._first_existing(
                        row,
                        "created_at",
                        "createdAt",
                        "date",
                    ),
                )
            )

        return tuple(result)

    # ==================================================================
    # MAIN SUMMARY
    # ==================================================================

    def get_summary(self) -> DashboardSummary:
        """Return a complete live dashboard summary."""
        (
            total_employees,
            active_employees,
            people_on_leave,
        ) = self._employee_counts()

        people_working = self._get_people_working()

        (
            total_work_assignments,
            active_work_assignments,
            tasks_in_progress,
            tasks_waiting_review,
        ) = self._work_assignment_counts()

        (
            total_quotes,
            active_quotes,
        ) = self._quote_counts()

        (
            total_orders,
            active_orders,
        ) = self._order_counts()

        tasks_due_today = self._tasks_due_today()
        tasks_overdue = self._tasks_overdue()
        completed_this_week = self._completed_this_week()

        pending_approvals = self._pending_approvals()
        upcoming_deadlines = self._upcoming_deadlines()

        # IMPORTANT:
        #
        # Active work is already the complete number of non-completed,
        # non-cancelled assignments.
        #
        # Do NOT calculate:
        #
        #     in_progress + active_work
        #
        # because that double-counts In Progress assignments.
        pending_tasks = active_work_assignments

        return DashboardSummary(
            people_working=people_working,
            people_on_leave=people_on_leave,
            people_on_site=people_working,

            tasks_due_today=tasks_due_today,
            tasks_overdue=tasks_overdue,
            tasks_waiting_review=tasks_waiting_review,
            completed_this_week=completed_this_week,

            pending_approvals=pending_approvals,
            upcoming_deadlines=upcoming_deadlines,

            latest_activity=self._latest_activity(),

            total_employees=total_employees,
            active_employees=active_employees,

            tasks_in_progress=tasks_in_progress,
            pending_tasks=pending_tasks,

            total_work_assignments=total_work_assignments,
            active_work_assignments=active_work_assignments,

            total_quotes=total_quotes,
            active_quotes=active_quotes,

            total_orders=total_orders,
            active_orders=active_orders,
        )

    # ==================================================================
    # BUSINESS LEAD
    # ==================================================================

    def get_business_lead_dashboard(
        self,
    ) -> BusinessLeadDashboard:
        """Return live Business Lead dashboard values."""
        work = self._collection("work_assignments")

        pending_approvals = self._count(
            self._collection("approvals"),
            {
                "status": {
                    "$in": [
                        "Pending",
                        "pending",
                    ]
                },
                "current_stage": {
                    "$in": [
                        "Business Lead",
                        "business lead",
                    ]
                },
            },
        )

        rfqs = self._count(
            work,
            {
                "category": {
                    "$in": [
                        "RFQ",
                        "Tender",
                    ]
                },
                "status": self._status_not_completed_cancelled(),
            },
        )

        supplier_registrations = self._count(
            work,
            {
                "category": {
                    "$in": [
                        "Supplier Registration",
                    ]
                },
                "status": self._status_not_completed_cancelled(),
            },
        )

        technical_jobs = self._count(
            work,
            {
                "category": "Technical",
                "status": self._status_not_completed_cancelled(),
            },
        )

        software_projects = self._count(
            work,
            {
                "category": {
                    "$in": [
                        "Software",
                        "Website",
                    ]
                },
                "status": self._status_not_completed_cancelled(),
            },
        )

        operational_alerts = self._count(
            self._collection("notifications"),
            {
                "is_read": False,
                "is_executive": {
                    "$ne": True,
                },
            },
        )

        active_work = self._count(
            work,
            self._work_assignment_filter_active(),
        )

        completed_week = self._completed_this_week()

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
        """Return the live Director dashboard."""
        work = self._collection("work_assignments")

        overdue = self._tasks_overdue()

        compliance = self._count(
            self._collection("notifications"),
            {
                "category": "Compliance",
                "is_read": False,
            },
        )

        inventory_alerts = self._count(
            self._collection("notifications"),
            {
                "category": "Inventory",
                "is_read": False,
            },
        )

        upcoming = self._upcoming_deadlines()

        financial_requests_waiting = self._count(
            self._collection("approvals"),
            {
                "status": {
                    "$in": [
                        "Pending",
                        "pending",
                    ]
                },
                "request_type": {
                    "$in": [
                        "Equipment",
                        "Software",
                        "Purchases",
                        "Budget",
                    ]
                },
            },
        )

        (
            _total_employees,
            active_employees,
            _people_on_leave,
        ) = self._employee_counts()

        working = self._get_people_working()

        active_work = self._count(
            work,
            self._work_assignment_filter_active(),
        )

        brief = self._latest_executive_brief()

        health = (
            "Attention required"
            if overdue > 0 or compliance > 0
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
                f"{working} of "
                f"{active_employees} active employees "
                f"currently working"
            ),
            financial_requests_waiting=financial_requests_waiting,
        )

    def _latest_executive_brief(self) -> str:
        """Return the latest Director executive brief."""
        notifications = self._collection("notifications")

        try:
            row = notifications.find_one(
                {
                    "recipient_role": {
                        "$in": [
                            "Director",
                            "director",
                        ]
                    },
                    "is_executive": True,
                },
                sort=[
                    ("createdAt", DESCENDING),
                    ("created_at", DESCENDING),
                ],
            )
        except Exception:
            row = None

        if row is None:
            return "No executive briefs require attention."

        message = self._first_existing(
            row,
            "message",
            "description",
            "text",
        )

        return (
            str(message)
            if message
            else "No executive briefs require attention."
        )

    # ==================================================================
    # OPTIONAL LIVE KPI API
    # ==================================================================

    def get_live_counts(self) -> dict[str, int]:
        """
        Return the dashboard's raw live counts.

        This is useful for dashboard cards and diagnostics.
        Every value comes from MongoDB.
        """
        summary = self.get_summary()

        return {
            "total_employees": summary.total_employees,
            "active_employees": summary.active_employees,
            "people_working": summary.people_working,
            "people_on_leave": summary.people_on_leave,

            "total_work_assignments": (
                summary.total_work_assignments
            ),
            "active_work_assignments": (
                summary.active_work_assignments
            ),
            "tasks_in_progress": (
                summary.tasks_in_progress
            ),
            "tasks_waiting_review": (
                summary.tasks_waiting_review
            ),
            "tasks_due_today": (
                summary.tasks_due_today
            ),
            "tasks_overdue": (
                summary.tasks_overdue
            ),

            "total_quotes": summary.total_quotes,
            "active_quotes": summary.active_quotes,

            "total_orders": summary.total_orders,
            "active_orders": summary.active_orders,

            "pending_approvals": (
                summary.pending_approvals
            ),
        }