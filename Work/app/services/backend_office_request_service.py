"""Backend API office request service for Mongo-backed office requests."""

from __future__ import annotations

from typing import Any

from app.models.office_request import OfficeRequest
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class BackendOfficeRequestService:
    """Drop-in OfficeRequestService replacement backed by the Backend API."""

    ITEMS = (
        "Printer Paper",
        "Pens",
        "Staples",
        "Printer Toner",
        "RFQ Dividers",
        "Stationery",
        "Ethernet Cable",
        "Mouse",
        "Keyboard",
        "Laptop",
        "Monitor",
    )

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend
        self._people_cache: list[str] | None = None

    def get_items(self) -> list[str]:
        try:
            data = self._backend.request("GET", "/api/office-requests/items")
            items = data.get("items") or []
            return [str(item) for item in items if item]
        except BackendAPIError:
            return list(self.ITEMS)

    def get_people_names(self) -> list[str]:
        if self._people_cache is not None:
            return self._people_cache
        try:
            data = self._backend.request("GET", "/api/employees")
            self._people_cache = [
                str(row.get("full_name") or "")
                for row in data.get("employees") or []
                if row.get("full_name")
            ]
        except BackendAPIError:
            self._people_cache = []
        return self._people_cache

    def get_requests(self) -> list[OfficeRequest]:
        data = self._backend.request("GET", "/api/office-requests")
        return [self._request_from_dict(row) for row in data.get("requests") or []]

    def create_request(
        self,
        item_name: str,
        quantity: int | str,
        requested_by: str,
        department: str,
        notes: str,
        requires_director: bool,
    ) -> OfficeRequest:
        payload = {
            "item_name": item_name,
            "quantity": int(quantity or 0),
            "requested_by": requested_by,
            "department": department,
            "notes": notes,
            "requires_director": requires_director,
        }
        data = self._backend.request("POST", "/api/office-requests", payload)
        return self._request_from_dict(data.get("request") or {})

    @staticmethod
    def _request_from_dict(data: dict[str, Any]) -> OfficeRequest:
        return OfficeRequest(
            id=data.get("id") or data.get("_id"),
            item_name=str(data.get("item_name") or ""),
            quantity=int(data.get("quantity") or 0),
            requested_by=str(data.get("requested_by") or ""),
            department=str(data.get("department") or ""),
            notes=str(data.get("notes") or ""),
            approval_id=data.get("approval_id"),
            approval_status=str(data.get("approval_status") or "Pending"),
            created_at=str(data.get("created_at") or "") or None,
        )
