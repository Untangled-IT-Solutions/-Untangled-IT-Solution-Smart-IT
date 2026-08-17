"""Approval workflow controller."""

from app.models.approval import ApprovalRequest
from app.services.approval_service import ApprovalService
from app.services.people_service import PeopleService


class ApprovalController:
    """Adapts approval forms and review actions to the workflow service."""

    REVIEWER_ROLES = ("Operations Manager", "Business Lead", "Director")

    def __init__(self, approval_service: ApprovalService, people_service: PeopleService) -> None:
        self._approval_service = approval_service
        self._people_service = people_service

    def create_request(
        self,
        title: str,
        request_type: str,
        description: str,
        requested_by: str,
        department: str,
        amount: str,
        requires_director: bool,
    ) -> ApprovalRequest:
        try:
            parsed_amount = float(amount) if amount.strip() else 0
        except ValueError as error:
            raise ValueError("Amount must be a number.") from error
        request = ApprovalRequest(
            id=None,
            title=title.strip(),
            request_type=request_type,
            description=description.strip(),
            requested_by=requested_by.strip(),
            department=department.strip(),
            amount=parsed_amount,
            status="Pending",
            current_stage="Operations Manager",
            requires_director=requires_director,
        )
        return self._approval_service.create_request(request)

    def get_approvals(self, status: str = "All") -> list[ApprovalRequest]:
        return self._approval_service.get_approvals(status)

    def approve(self, approval_id: int, reviewer_name: str, reviewer_role: str) -> ApprovalRequest:
        return self._approval_service.approve(approval_id, reviewer_name, reviewer_role)

    def reject(
        self,
        approval_id: int,
        reviewer_name: str,
        reviewer_role: str,
        reason: str,
    ) -> ApprovalRequest:
        return self._approval_service.reject(approval_id, reviewer_name, reviewer_role, reason)

    def get_request_types(self) -> list[str]:
        return list(self._approval_service.REQUEST_TYPES)

    def get_people_names(self) -> list[str]:
        return self._people_service.get_employee_names()

    def get_departments(self) -> list[str]:
        return self._people_service.get_departments()
