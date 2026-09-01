"""Approval workflow service."""

import sqlite3
from pathlib import Path

from app.database.database import Database
from app.models.approval import ApprovalRequest
from app.services.notification_service import NotificationService


class ApprovalService:
    """Moves requests through Employee, Operations, Business Lead, and Director stages."""

    REQUEST_TYPES = (
        "Office Supplies",
        "Equipment",
        "Leave",
        "Software",
        "Purchases",
        "Budget",
    )
    _STAGES = ("Operations Manager", "Business Lead", "Director")

    def __init__(
        self,
        database: Database,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._database = database
        self._notifications = notification_service

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def create_request(self, request: ApprovalRequest) -> ApprovalRequest:
        """Create a request at the Operations Manager review stage."""
        self._validate_request(request)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO approvals (
                    title, request_type, description, requested_by, department, amount,
                    status, current_stage, requires_director, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'Pending', 'Operations Manager', ?, CURRENT_TIMESTAMP);
                """,
                (
                    request.title,
                    request.request_type,
                    request.description,
                    request.requested_by,
                    request.department,
                    request.amount,
                    int(request.requires_director),
                ),
            )
            connection.commit()
            saved = self._get_by_id(connection, int(cursor.lastrowid))

        self._record_transition(saved, "submitted", "Operations Manager")
        return saved

    def get_approvals(self, status: str = "All") -> list[ApprovalRequest]:
        """Return approval requests, optionally filtered by state."""
        query = "SELECT * FROM approvals"
        parameters: tuple[object, ...] = ()
        if status != "All":
            query += " WHERE status = ?"
            parameters = (status,)
        query += " ORDER BY datetime(updated_at) DESC, id DESC;"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_request(row) for row in rows]

    def get_approval(self, approval_id: int) -> ApprovalRequest | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM approvals WHERE id = ?;", (approval_id,)).fetchone()
        return self._row_to_request(row) if row is not None else None

    def approve(self, approval_id: int, reviewer_name: str, reviewer_role: str) -> ApprovalRequest:
        """Approve the current required stage and advance the request."""
        with self._connect() as connection:
            request = self._get_by_id(connection, approval_id)
            self._validate_reviewer(request, reviewer_role)
            field = {
                "Operations Manager": "manager_approved_by",
                "Business Lead": "business_approved_by",
                "Director": "director_approved_by",
            }[reviewer_role]
            next_stage = self._next_stage(request, reviewer_role)
            status = "Approved" if next_stage == "Completed" else "Pending"
            connection.execute(
                f"""
                UPDATE approvals
                SET {field} = ?, current_stage = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (reviewer_name.strip(), next_stage, status, approval_id),
            )
            connection.commit()
            updated = self._get_by_id(connection, approval_id)

        self._record_transition(updated, "approved", next_stage)
        return updated

    def reject(
        self,
        approval_id: int,
        reviewer_name: str,
        reviewer_role: str,
        reason: str,
    ) -> ApprovalRequest:
        """Reject the current stage and close the request."""
        if not reason.strip():
            raise ValueError("A rejection reason is required.")
        with self._connect() as connection:
            request = self._get_by_id(connection, approval_id)
            self._validate_reviewer(request, reviewer_role)
            connection.execute(
                """
                UPDATE approvals
                SET status = 'Rejected', current_stage = 'Completed',
                    rejection_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (f"{reviewer_name.strip()}: {reason.strip()}", approval_id),
            )
            connection.commit()
            updated = self._get_by_id(connection, approval_id)

        self._record_transition(updated, "rejected", "Completed")
        return updated

    def get_pending_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM approvals WHERE status = 'Pending';").fetchone()[0])

    def _record_transition(
        self,
        request: ApprovalRequest,
        action: str,
        next_stage: str,
    ) -> None:
        if self._notifications is None:
            return
        description = f"Approval {action}: {request.title}"
        self._notifications.record_activity("Approvals", description, "Approval", request.id)
        if next_stage == "Director":
            self._notifications.notify_executive(
                "Executive approval brief",
                f"{request.request_type}: {request.title} requires Director review.",
                "Approvals",
                "Approval",
                request.id,
            )
        elif next_stage != "Completed":
            self._notifications.notify_operational(
                (next_stage,),
                "Approval requires review",
                f"{request.request_type}: {request.title} is awaiting your review.",
                "Approvals",
                "Approval",
                request.id,
            )
        else:
            self._notifications.notify_operational(
                ("Operations Manager", request.requested_by),
                "Approval update",
                f"{request.title} was {request.status.lower()}.",
                "Approvals",
                "Approval",
                request.id,
            )

    @classmethod
    def _next_stage(cls, request: ApprovalRequest, reviewer_role: str) -> str:
        if reviewer_role == "Operations Manager":
            return "Business Lead"
        if reviewer_role == "Business Lead":
            return "Director" if request.requires_director else "Completed"
        return "Completed"

    @classmethod
    def _validate_reviewer(cls, request: ApprovalRequest, reviewer_role: str) -> None:
        if request.status != "Pending":
            raise ValueError("Only pending approval requests can be reviewed.")
        if reviewer_role not in cls._STAGES or request.current_stage != reviewer_role:
            raise ValueError(f"This request is awaiting {request.current_stage} review.")

    @classmethod
    def _validate_request(cls, request: ApprovalRequest) -> None:
        if not request.title.strip():
            raise ValueError("Request title is required.")
        if request.request_type not in cls.REQUEST_TYPES:
            raise ValueError("Select a valid approval type.")
        if not request.requested_by.strip() or not request.department.strip():
            raise ValueError("Requestor and department are required.")
        if request.amount < 0:
            raise ValueError("Amount cannot be negative.")

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    def _get_by_id(self, connection: sqlite3.Connection, approval_id: int) -> ApprovalRequest:
        row = connection.execute("SELECT * FROM approvals WHERE id = ?;", (approval_id,)).fetchone()
        if row is None:
            raise ValueError("Approval request was not found.")
        return self._row_to_request(row)

    @staticmethod
    def _row_to_request(row: sqlite3.Row) -> ApprovalRequest:
        return ApprovalRequest(
            id=row["id"],
            title=row["title"],
            request_type=row["request_type"],
            description=row["description"] or "",
            requested_by=row["requested_by"],
            department=row["department"],
            amount=float(row["amount"] or 0),
            status=row["status"],
            current_stage=row["current_stage"],
            requires_director=bool(row["requires_director"]),
            submitted_at=row["submitted_at"],
            updated_at=row["updated_at"],
            manager_approved_by=row["manager_approved_by"] or "",
            business_approved_by=row["business_approved_by"] or "",
            director_approved_by=row["director_approved_by"] or "",
            rejection_reason=row["rejection_reason"] or "",
        )
