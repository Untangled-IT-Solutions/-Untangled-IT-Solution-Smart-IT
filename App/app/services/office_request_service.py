"""Office request persistence and approval integration service."""

import sqlite3
from pathlib import Path

from app.database.database import Database
from app.models.approval import ApprovalRequest
from app.models.office_request import OfficeRequest
from app.services.approval_service import ApprovalService
from app.services.notification_service import NotificationService


class OfficeRequestService:
    """Creates office requests and links each one to the standard approval workflow."""

    ITEMS = (
        "Printer Paper", "Pens", "Staples", "Printer Toner", "RFQ Dividers",
        "Stationery", "Ethernet Cable", "Mouse", "Keyboard", "Laptop", "Monitor",
    )

    def __init__(
        self,
        database: Database,
        approval_service: ApprovalService,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._database = database
        self._approval_service = approval_service
        self._notifications = notification_service

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def create_request(
        self,
        item_name: str,
        quantity: int,
        requested_by: str,
        department: str,
        notes: str,
        requires_director: bool,
    ) -> OfficeRequest:
        """Create an office request and submit it through the central approval engine."""
        if item_name not in self.ITEMS:
            raise ValueError("Select a valid office item.")
        if quantity < 1:
            raise ValueError("Quantity must be at least one.")
        approval = self._approval_service.create_request(
            ApprovalRequest(
                id=None,
                title=f"Office request: {quantity} x {item_name}",
                request_type="Office Supplies",
                description=notes.strip() or f"Request for {quantity} x {item_name}",
                requested_by=requested_by.strip(),
                department=department.strip(),
                amount=0,
                status="Pending",
                current_stage="Operations Manager",
                requires_director=requires_director,
            )
        )
        if approval.id is None:
            raise ValueError("Approval request could not be created.")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO office_requests (
                    item_name, quantity, requested_by, department, notes, approval_id
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (item_name, quantity, requested_by.strip(), department.strip(), notes.strip(), approval.id),
            )
            connection.commit()
            row = connection.execute(
                """
                SELECT office_requests.*, approvals.status AS approval_status
                FROM office_requests
                JOIN approvals ON approvals.id = office_requests.approval_id
                WHERE office_requests.id = ?;
                """,
                (cursor.lastrowid,),
            ).fetchone()
        request = self._row_to_request(row)
        if self._notifications is not None:
            self._notifications.record_activity(
                "Inventory", f"Office request submitted: {request.quantity} x {request.item_name}",
                "OfficeRequest", request.id
            )
        return request

    def get_requests(self) -> list[OfficeRequest]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT office_requests.*, approvals.status AS approval_status
                FROM office_requests
                JOIN approvals ON approvals.id = office_requests.approval_id
                ORDER BY datetime(office_requests.created_at) DESC, office_requests.id DESC;
                """
            ).fetchall()
        return [self._row_to_request(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    @staticmethod
    def _row_to_request(row: sqlite3.Row) -> OfficeRequest:
        return OfficeRequest(
            id=row["id"], item_name=row["item_name"], quantity=int(row["quantity"]),
            requested_by=row["requested_by"], department=row["department"],
            notes=row["notes"] or "", approval_id=row["approval_id"],
            approval_status=row["approval_status"], created_at=row["created_at"]
        )
