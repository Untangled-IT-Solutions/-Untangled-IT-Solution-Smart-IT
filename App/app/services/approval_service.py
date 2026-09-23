"""Approvals – Backend API only."""

from __future__ import annotations

from typing import Any, List

from app.models.approval import ApprovalRequest
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class ApprovalService:
    REQUEST_TYPES = [
        "Purchase",
        "Travel",
        "Overtime",
        "Budget",
        "General",
    ]

    def __init__(self, backend: BackendAPIClient, people_service: Any = None) -> None:
        self._backend = backend
        self._people = people_service

    def _to_model(self, raw: dict) -> ApprovalRequest:
        amount = raw.get("amount") or 0
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0.0
        return ApprovalRequest(
            id=raw.get("id") or raw.get("_id"),
            title=str(raw.get("title") or ""),
            request_type=str(raw.get("request_type") or raw.get("type") or "General"),
            description=str(raw.get("description") or ""),
            requested_by=str(raw.get("requested_by") or raw.get("requester") or ""),
            department=str(raw.get("department") or ""),
            amount=amount,
            status=str(raw.get("status") or "Pending"),
            current_stage=str(raw.get("current_stage") or raw.get("stage") or "Manager"),
            requires_director=bool(raw.get("requires_director")),
            submitted_at=raw.get("submitted_at") or raw.get("created_at"),
            updated_at=raw.get("updated_at"),
            manager_approved_by=str(raw.get("manager_approved_by") or ""),
            business_approved_by=str(raw.get("business_approved_by") or ""),
            director_approved_by=str(raw.get("director_approved_by") or ""),
            rejection_reason=str(raw.get("rejection_reason") or ""),
            leave_type=str(raw.get("leave_type") or ""),
            start_date=str(raw.get("start_date") or ""),
            end_date=str(raw.get("end_date") or ""),
            document_ids=tuple(str(value) for value in (raw.get("document_ids") or [])),
            raw=raw,
        )

    def get_approvals(self, status: str = "All") -> List[ApprovalRequest]:
        try:
            q = f"?status={status}" if status and status != "All" else ""
            data = self._backend.request("GET", f"/api/approvals{q}")
            items = data.get("approvals") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                items = data
            result = [self._to_model(i) for i in items if isinstance(i, dict)]
            if status and status != "All":
                result = [a for a in result if a.status.lower() == status.lower()]
            return result
        except BackendAPIError as exc:
            print(f"⚠️ approvals fetch failed: {exc}")
            return []

    def get_request_types(self) -> list:
        return list(self.REQUEST_TYPES)

    def get_people_names(self) -> list:
        if self._people is not None:
            try:
                return self._people.get_names()
            except Exception:
                pass
        return []

    def get_departments(self) -> list:
        if self._people is not None:
            try:
                return self._people.get_departments()
            except Exception:
                pass
        return []

    def create_request(
        self,
        title: str,
        request_type: str,
        description: str,
        requested_by: str,
        department: str,
        amount: str,
        requires_director: bool,
    ) -> dict:
        payload = {
            "title": title,
            "request_type": request_type,
            "description": description,
            "requested_by": requested_by,
            "department": department,
            "amount": amount,
            "requires_director": requires_director,
        }
        return self._backend.request("POST", "/api/approvals", payload)

    def approve(self, approval_id: int, reviewer: str, stage: str) -> dict:
        return self._backend.request(
            "POST",
            f"/api/approvals/{approval_id}/approve",
            {"reviewer": reviewer, "stage": stage},
        )

    def reject(self, approval_id: int, reviewer: str, stage: str, reason: str) -> dict:
        return self._backend.request(
            "POST",
            f"/api/approvals/{approval_id}/reject",
            {"reviewer": reviewer, "stage": stage, "reason": reason},
        )

    def submit_leave(
        self,
        leave_type: str,
        start_date: str,
        end_date: str,
        reason: str,
        document_paths: list[str],
        requires_director: bool,
    ) -> dict:
        document_ids = []
        for path in document_paths:
            document_type = "Doctor note" if leave_type == "Sick" else "Supporting Document"
            uploaded = self._backend.upload_document(path, document_type)
            document = uploaded.get("document") or {}
            document_id = document.get("id") or document.get("_id")
            if not document_id:
                raise RuntimeError("The server did not return the uploaded document ID.")
            document_ids.append(str(document_id))
        return self._backend.request(
            "POST",
            "/api/leave",
            {
                "leave_type": leave_type,
                "start_date": start_date,
                "end_date": end_date,
                "reason": reason,
                "document_ids": document_ids,
                "requires_director": requires_director,
            },
        )

    def download_document(self, document_id: str) -> dict:
        return self._backend.download_document(document_id)
