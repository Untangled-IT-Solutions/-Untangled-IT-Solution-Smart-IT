"""Backend API HR leave and sick-note service."""

from __future__ import annotations

from typing import Any

from app.models.approval import ApprovalRequest
from app.services.backend_api_client import BackendAPIClient


class BackendHRService:
    """Expose Mongo-backed HR requests as approval-style records."""

    REQUEST_TYPES = ("Leave", "Sick Leave")

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def get_requests(self, status: str = "All") -> list[ApprovalRequest]:
        path = "/api/hr/leave-requests"
        if status != "All":
            path = f"{path}?status={status}"
        data = self._backend.request("GET", path)
        return [self._request_from_dict(row) for row in data.get("requests") or []]

    def create_request(
        self,
        request_type: str,
        start_date: str,
        end_date: str,
        reason: str,
        department: str = "",
        sick_note: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        payload = {
            "request_type": request_type if request_type in self.REQUEST_TYPES else "Leave",
            "start_date": start_date,
            "end_date": end_date or start_date,
            "reason": reason,
            "department": department,
            "sick_note": sick_note,
        }
        data = self._backend.request("POST", "/api/hr/leave-requests", payload)
        return self._request_from_dict(data.get("request") or {})

    def approve(self, request_id: Any, reviewer: str, notes: str = "") -> ApprovalRequest:
        return self._review(request_id, "Approved", notes)

    def reject(self, request_id: Any, reviewer: str, notes: str = "") -> ApprovalRequest:
        return self._review(request_id, "Rejected", notes)

    def _review(self, request_id: Any, status: str, notes: str) -> ApprovalRequest:
        clean_id = self._clean_id(request_id)
        data = self._backend.request(
            "PATCH",
            f"/api/hr/leave-requests/{clean_id}",
            {"status": status, "evaluation_notes": notes},
        )
        return self._request_from_dict(data.get("request") or {})

    @staticmethod
    def _clean_id(request_id: Any) -> str:
        value = str(request_id)
        return value[3:] if value.startswith("hr:") else value

    @classmethod
    def _request_from_dict(cls, data: dict[str, Any]) -> ApprovalRequest:
        request_id = data.get("id") or data.get("_id")
        request_type = str(data.get("request_type") or "Leave")
        start = str(data.get("start_date") or "")
        end = str(data.get("end_date") or start)
        reason = str(data.get("reason") or "")
        sick_note = data.get("sick_note") if isinstance(data.get("sick_note"), dict) else None
        note_text = ""
        if sick_note:
            name = sick_note.get("file_name") or "attached sick note"
            status = sick_note.get("status") or "Pending Evaluation"
            note_text = f"\nSick note: {name} ({status})"

        return ApprovalRequest(
            id=f"hr:{request_id}" if request_id else None,
            title=str(data.get("title") or f"{request_type} request"),
            request_type=request_type,
            description=f"{start} to {end}\n{reason}{note_text}".strip(),
            requested_by=str(data.get("employee_name") or ""),
            department=str(data.get("department") or ""),
            amount=0,
            status=str(data.get("status") or "Pending"),
            current_stage=str(data.get("current_stage") or "Operations Manager"),
            requires_director=False,
            submitted_at=str(data.get("created_at") or "") or None,
            updated_at=str(data.get("updated_at") or "") or None,
            manager_approved_by=str(data.get("reviewed_by") or ""),
            rejection_reason=str(data.get("evaluation_notes") or ""),
        )
