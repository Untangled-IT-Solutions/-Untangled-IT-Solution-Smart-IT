# app/controllers/approval_controller.py
"""Approval controller."""

from typing import Any

from app.models.approval import ApprovalRequest
from app.services.approval_service import ApprovalService
from app.services.backend_hr_service import BackendHRService
from app.services.mongo_notification_service import MongoNotificationService
from app.services.people_service import PeopleService


class ApprovalController:
    """Controls approval operations."""

    def __init__(
        self,
        approval_service: ApprovalService,
        notification_service: MongoNotificationService,
        people_service: PeopleService | None = None,
        hr_service: BackendHRService | None = None,
    ) -> None:
        self._service = approval_service
        self._notification_service = notification_service
        self._people_service = people_service
        self._hr_service = hr_service

    def get_approvals(self, status: str = "All") -> list:
        """Get approvals with optional status filter."""
        approvals = list(self._service.get_approvals(status))
        if self._hr_service is not None:
            approvals.extend(self._hr_service.get_requests(status))
        return sorted(
            approvals,
            key=lambda item: str(item.updated_at or item.submitted_at or ""),
            reverse=True,
        )

    def get_request_types(self) -> list:
        """Get list of request types."""
        values = list(getattr(self._service, "REQUEST_TYPES", ()))
        if self._hr_service is not None:
            values.extend(value for value in self._hr_service.REQUEST_TYPES if value not in values)
        return values

    def get_people_names(self) -> list:
        """Get list of people names."""
        if self._people_service is None:
            return []
        if hasattr(self._people_service, "get_employee_names"):
            return self._people_service.get_employee_names()
        return [person.full_name for person in self._people_service.get_employees()]

    def get_departments(self) -> list:
        """Get list of departments."""
        if self._people_service is None:
            return []
        return self._people_service.get_departments()

    def create_request(self, title: str, request_type: str, description: str,
                       requested_by: str, department: str, amount: str,
                       requires_director: bool, start_date: str = "",
                       end_date: str = "", sick_note: dict[str, Any] | None = None) -> dict:
        """Create a new approval request."""
        if request_type in ("Leave", "Sick Leave") and self._hr_service is not None:
            return self._hr_service.create_request(
                request_type=request_type,
                start_date=start_date,
                end_date=end_date,
                reason=description,
                department=department,
                sick_note=sick_note,
            )

        return self._service.create_request(
            ApprovalRequest(
                id=None,
                title=title,
                request_type=request_type,
                description=description,
                requested_by=requested_by,
                department=department,
                amount=float(amount or 0),
                status="Pending",
                current_stage="Operations Manager",
                requires_director=requires_director,
            )
        )

    def approve(self, approval_id: Any, reviewer: str, stage: str) -> dict:
        """Approve a request."""
        if str(approval_id).startswith("hr:") and self._hr_service is not None:
            return self._hr_service.approve(approval_id, reviewer)
        return self._service.approve(approval_id, reviewer, stage)

    def reject(self, approval_id: Any, reviewer: str, stage: str, reason: str) -> dict:
        """Reject a request."""
        if str(approval_id).startswith("hr:") and self._hr_service is not None:
            return self._hr_service.reject(approval_id, reviewer, reason)
        return self._service.reject(approval_id, reviewer, stage, reason)
