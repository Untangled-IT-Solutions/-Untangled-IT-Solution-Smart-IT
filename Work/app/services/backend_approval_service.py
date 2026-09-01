"""Backend API approval service for Mongo-backed approval workflows."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from app.models.approval import ApprovalRequest
from app.services.backend_api_client import BackendAPIClient


class BackendApprovalService:
    """Drop-in ApprovalService replacement backed by the Backend API."""

    REQUEST_TYPES = (
        "General",
        "Office Supplies",
        "Equipment",
        "Software",
        "Purchases",
        "Budget",
        "Task Approval",
        "Director Review",
    )

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def create_request(self, request: ApprovalRequest) -> ApprovalRequest:
        payload = {
            "title": request.title,
            "request_type": request.request_type,
            "description": request.description,
            "requested_by": request.requested_by,
            "department": request.department,
            "amount": request.amount,
            "requires_director": request.requires_director,
        }
        data = self._backend.request("POST", "/api/approvals", payload)
        return self._request_from_dict(data.get("approval") or {})

    def get_approvals(self, status: str = "All") -> list[ApprovalRequest]:
        params = {}
        if status != "All":
            params["status"] = status
        query = f"?{urlencode(params)}" if params else ""
        data = self._backend.request("GET", f"/api/approvals{query}")
        return [self._request_from_dict(row) for row in data.get("approvals") or []]

    def get_approval(self, approval_id: Any) -> ApprovalRequest | None:
        data = self._backend.request("GET", f"/api/approvals/{approval_id}")
        approval = data.get("approval")
        return self._request_from_dict(approval) if approval else None

    def approve(self, approval_id: Any, reviewer_name: str, reviewer_role: str) -> ApprovalRequest:
        return self._review(approval_id, "approve", reviewer_name, reviewer_role)

    def reject(
        self,
        approval_id: Any,
        reviewer_name: str,
        reviewer_role: str,
        reason: str,
    ) -> ApprovalRequest:
        return self._review(approval_id, "reject", reviewer_name, reviewer_role, reason)

    def get_pending_count(self) -> int:
        return len(self.get_approvals("Pending"))

    def _review(
        self,
        approval_id: Any,
        decision: str,
        reviewer_name: str,
        reviewer_role: str,
        reason: str = "",
    ) -> ApprovalRequest:
        payload = {
            "decision": decision,
            "reviewer": reviewer_name,
            "stage": reviewer_role,
            "reason": reason,
        }
        data = self._backend.request("PATCH", f"/api/approvals/{approval_id}", payload)
        return self._request_from_dict(data.get("approval") or {})

    @staticmethod
    def _request_from_dict(data: dict[str, Any]) -> ApprovalRequest:
        return ApprovalRequest(
            id=data.get("id") or data.get("_id"),
            title=str(data.get("title") or ""),
            request_type=str(data.get("request_type") or "General"),
            description=str(data.get("description") or ""),
            requested_by=str(data.get("requested_by") or ""),
            department=str(data.get("department") or ""),
            amount=float(data.get("amount") or 0),
            status=str(data.get("status") or "Pending"),
            current_stage=str(data.get("current_stage") or "Operations Manager"),
            requires_director=bool(data.get("requires_director")),
            submitted_at=str(data.get("submitted_at") or "") or None,
            updated_at=str(data.get("updated_at") or "") or None,
            manager_approved_by=str(data.get("manager_approved_by") or ""),
            business_approved_by=str(data.get("business_approved_by") or ""),
            director_approved_by=str(data.get("director_approved_by") or ""),
            rejection_reason=str(data.get("rejection_reason") or ""),
        )
