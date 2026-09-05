"""Notifications – Backend API only."""

from __future__ import annotations

from typing import Any, List, Optional

from app.models.notification import Notification
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class NotificationService:
    """Backend-backed notification surface (replaces MongoNotificationService)."""

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def _to_model(self, raw: dict) -> Notification:
        return Notification(
            id=raw.get("id") or raw.get("_id"),
            recipient_role=str(raw.get("recipient_role") or raw.get("role") or "All"),
            title=str(raw.get("title") or ""),
            message=str(raw.get("message") or raw.get("body") or ""),
            category=str(raw.get("category") or "General"),
            reference_type=str(raw.get("reference_type") or ""),
            reference_id=raw.get("reference_id"),
            is_executive=bool(raw.get("is_executive")),
            is_read=bool(raw.get("is_read") or raw.get("read")),
            created_at=raw.get("created_at") or raw.get("createdAt"),
        )

    def get_notifications(self, role: str = "All", unread_only: bool = False) -> List[Notification]:
        try:
            params = []
            if role and role != "All":
                params.append(f"role={role}")
            if unread_only:
                params.append("unread=1")
            q = ("?" + "&".join(params)) if params else ""
            data = self._backend.request("GET", f"/api/notifications{q}")
            items = data.get("notifications") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                items = data
            result = [self._to_model(i) for i in items if isinstance(i, dict)]
            if unread_only:
                result = [n for n in result if not n.is_read]
            if role and role != "All":
                result = [
                    n for n in result
                    if n.recipient_role in (role, "All", "") or not n.recipient_role
                ]
            result = self._dedupe(result)
            # Newest first when timestamps exist
            result.sort(key=lambda n: n.created_at or "", reverse=True)
            return result
        except BackendAPIError as exc:
            print(f"⚠️ notifications fetch failed: {exc}")
            return []

    @staticmethod
    def _dedupe(items: List[Notification]) -> List[Notification]:
        """Collapse identical assignment notices (backend + client both posting)."""
        seen: set[str] = set()
        out: List[Notification] = []
        for n in items:
            key = "|".join(
                [
                    (n.title or "").strip().lower(),
                    (n.message or "").strip().lower(),
                    str(n.reference_type or ""),
                    str(n.reference_id or ""),
                    str(n.is_read),
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(n)
        return out

    def notify_operational(
        self,
        recipient_roles: list,
        title: str,
        message: str,
        category: str,
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        for role in recipient_roles or ["Staff"]:
            payload = {
                "title": title,
                "message": message,
                "category": category,
                "recipient_role": role,
                "reference_type": reference_type,
                "reference_id": reference_id,
            }
            try:
                self._backend.request("POST", "/api/notifications", payload)
            except BackendAPIError as exc:
                print(f"⚠️ notify_operational failed for {role}: {exc}")



    def count_unread(self, role: str = "All") -> int:
        """Return number of unread notifications (for sidebar badge)."""
        try:
            items = self.get_notifications(role=role, unread_only=True)
            return len(items)
        except Exception:
            try:
                return len([n for n in self.get_notifications(role=role) if not n.is_read])
            except Exception:
                return 0

# Backward-compatible alias used by older controllers
MongoNotificationService = NotificationService
