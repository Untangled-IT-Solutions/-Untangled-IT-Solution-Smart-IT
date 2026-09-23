# app/controllers/approval_controller.py
"""Approval controller."""

from typing import Any, Callable, Optional

from app.services.approval_service import ApprovalService
from app.services.mongo_notification_service import MongoNotificationService


class ApprovalController:
    """Controls approval operations."""

    def __init__(
        self,
        approval_service: ApprovalService,
        notification_service: MongoNotificationService,
        get_current_account: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._service = approval_service
        self._notification_service = notification_service
        self._get_current_account = get_current_account

    def current_account(self):
        return self._get_current_account() if self._get_current_account else None

    def can_review(self, request) -> bool:
        account = self.current_account()
        role = getattr(account, "role", None) or "Staff"
        name = (getattr(account, "full_name", None) or "").strip().casefold()
        if request.status != "Pending" or name == (request.requested_by or "").strip().casefold():
            return False
        allowed = {
            "Manager": {"Operations Manager", "Super Admin"},
            "Business": {"Business Lead", "Super Admin"},
            "Director": {"Director", "Super Admin"},
        }
        return role in allowed.get(request.current_stage, set())

    def get_approvals(self, status: str = "All") -> list:
        """Get approvals with optional status filter."""
        return self._service.get_approvals(status)

    def get_request_types(self) -> list:
        """Get list of request types."""
        return self._service.get_request_types()

    def get_people_names(self) -> list:
        """Get list of people names."""
        return self._service.get_people_names()

    def get_departments(self) -> list:
        """Get list of departments."""
        return self._service.get_departments()

    def create_request(self, title: str, request_type: str, description: str,
                       requested_by: str, department: str, amount: str,
                       requires_director: bool) -> dict:
        """Create a new approval request."""
        return self._service.create_request(
            title, request_type, description, requested_by,
            department, amount, requires_director
        )

    def approve(self, approval_id: int, reviewer: str, stage: str) -> dict:
        """Approve a request."""
        return self._service.approve(approval_id, reviewer, stage)

    def reject(self, approval_id: int, reviewer: str, stage: str, reason: str) -> dict:
        """Reject a request."""
        return self._service.reject(approval_id, reviewer, stage, reason)

    def submit_leave(self, leave_type, start_date, end_date, reason, document_paths, requires_director):
        return self._service.submit_leave(
            leave_type, start_date, end_date, reason, document_paths, requires_director
        )

    def download_document(self, document_id: str):
        return self._service.download_document(document_id)
