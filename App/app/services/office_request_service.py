"""Office requests – Backend API only."""

from __future__ import annotations

from typing import Any, List

from app.models.office_request import OfficeRequest
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class OfficeRequestService:
    DEFAULT_ITEMS = [
        "Stationery",
        "Toner / Ink",
        "Keyboard",
        "Mouse",
        "Monitor",
        "Headset",
        "Other",
    ]

    def __init__(self, backend: BackendAPIClient, people_service: Any = None) -> None:
        self._backend = backend
        self._people = people_service

    def _to_model(self, raw: dict) -> OfficeRequest:
        qty = raw.get("quantity") or 1
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            qty = 1
        return OfficeRequest(
            id=raw.get("id") or raw.get("_id"),
            item_name=str(raw.get("item_name") or raw.get("item") or ""),
            quantity=qty,
            requested_by=str(raw.get("requested_by") or ""),
            department=str(raw.get("department") or ""),
            notes=str(raw.get("notes") or ""),
            approval_id=raw.get("approval_id") or 0,
            approval_status=str(raw.get("approval_status") or raw.get("status") or "Pending"),
            created_at=raw.get("created_at"),
        )

    def get_requests(self) -> List[OfficeRequest]:
        try:
            data = self._backend.request("GET", "/api/office-requests")
            items = data.get("requests") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                items = data
            return [self._to_model(i) for i in items if isinstance(i, dict)]
        except BackendAPIError as exc:
            print(f"⚠️ office requests fetch failed: {exc}")
            return []

    def get_items(self) -> list:
        try:
            data = self._backend.request("GET", "/api/office-requests/items")
            items = data.get("items") or data.get("data") or []
            if items:
                return list(items)
        except BackendAPIError:
            pass
        return list(self.DEFAULT_ITEMS)

    def get_people_names(self) -> list:
        if self._people is not None:
            try:
                return self._people.get_names()
            except Exception:
                pass
        return []

    def create_request(
        self,
        item: str,
        quantity: str,
        requested_by: str,
        department: str,
        notes: str,
        requires_director: bool,
    ) -> dict:
        payload = {
            "item": item,
            "item_name": item,
            "quantity": quantity,
            "requested_by": requested_by,
            "department": department,
            "notes": notes,
            "requires_director": requires_director,
        }
        return self._backend.request("POST", "/api/office-requests", payload)
