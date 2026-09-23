"""Notifications – Backend API only (robust mark-as-read)."""
from __future__ import annotations

from typing import Any, List, Optional
import threading

from app.models.notification import Notification
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class NotificationService:
    """Backend-backed notification surface."""

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend
        self._last_results: dict[tuple[str, bool], List[Notification]] = {}
        self._last_unread_count: Optional[int] = None
        self.last_error: Optional[str] = None
        self.is_stale = False

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
            is_read=bool(raw.get("is_read") or raw.get("read") or raw.get("isRead")),
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
            separator = "&" if q else "?"
            data = self._backend.request("GET", f"/api/notifications{q}{separator}limit=100")
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
            result.sort(key=lambda n: n.created_at or "", reverse=True)
            self._last_results[(role, unread_only)] = result
            self.last_error = None
            self.is_stale = False
            return result
        except BackendAPIError as exc:
            self.last_error = str(exc)
            self.is_stale = True
            cached = self._last_results.get((role, unread_only))
            if cached is not None:
                return list(cached)
            raise

    def mark_read(self, notification_id: str) -> bool:
        """Mark a single notification as read using the canonical API contract."""
        if not notification_id:
            print("⚠️ mark_read: empty id")
            return False

        nid = str(notification_id).strip()
        data = self._backend.request("POST", f"/api/notifications/{nid}/read")
        return bool(isinstance(data, dict) and data.get("success"))

    def mark_all_read(self, role: str = "All") -> int:
        """Mark all unread notifications as read. Returns how many were marked."""
        print(f"📋 mark_all_read(role={role})")

        payload = {"role": role} if role and role != "All" else {}

        # Prefer the real backend routes. mark-all-read is now an alias on the server.
        # Do NOT treat a bare success with no count as "1 marked" – that hid the old bug.
        bulk_attempts = [
            ("POST", "/api/notifications/mark-all-read", payload),
            ("POST", "/api/notifications/read-all", payload),
            ("PATCH", "/api/notifications/mark-all-read", payload),
            ("PATCH", "/api/notifications/read-all", payload),
        ]

        for method, path, body in bulk_attempts:
            try:
                data = self._backend.request(method, path, body)
                if not isinstance(data, dict):
                    continue
                count = int(
                    data.get("count")
                    or data.get("marked")
                    or data.get("updated")
                    or data.get("modifiedCount")
                    or data.get("modified")
                    or 0
                )
                matched = int(data.get("matched") or data.get("matchedCount") or 0)
                print(f"✅ mark_all_read via {method} {path} → count={count} matched={matched}")
                # Real update happened
                if count > 0 or matched > 0:
                    return max(count, matched)
                # Explicit success with 0 is still a valid "nothing left to mark"
                if data.get("success") is True or data.get("ok") is True:
                    return count
            except BackendAPIError as exc:
                print(f"⚠️ {method} {path} failed: {exc}")
                continue

        # Fallback: mark one-by-one
        items = self.get_notifications(role=role, unread_only=True)
        print(f"📋 Fallback: marking {len(items)} unread notification(s) one by one")
        count = 0
        for n in items:
            nid = getattr(n, "id", None)
            if nid and self.mark_read(str(nid)):
                count += 1
        print(f"✅ Marked {count} notification(s) as read (one-by-one)")
        return count

    @staticmethod
    def _dedupe(items: List[Notification]) -> List[Notification]:
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

    def notify_user(
        self,
        user_name: str,
        message: str,
        category: str = "General",
        title: str = "",
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        """Send a notification targeted at a specific user/username."""
        payload = {
            "title": title or "Notification",
            "message": message,
            "category": category,
            "recipient_name": user_name,
            "recipient": user_name,
            "recipient_username": user_name,
            "user_name": user_name,
            "reference_type": reference_type,
            "reference_id": reference_id,
        }
        try:
            self._backend.request("POST", "/api/notifications", payload)
        except BackendAPIError as exc:
            print(f"⚠️ notify_user failed for {user_name}: {exc}")

    def notify_executive(
        self,
        title: str,
        message: str,
        category: str = "Quote",
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        self.notify_operational(
            recipient_roles=["Director"],
            title=title,
            message=message,
            category=category,
            reference_type=reference_type,
            reference_id=reference_id,
        )

    def count_unread(self, role: str = "All") -> int:
        try:
            data = self._backend.request("GET", "/api/notifications/unread-count")
            count = int(data.get("count") or data.get("unread") or 0)
            self._last_unread_count = count
            self.last_error = None
            self.is_stale = False
            return count
        except BackendAPIError as exc:
            self.last_error = str(exc)
            self.is_stale = True
            if self._last_unread_count is not None:
                return self._last_unread_count
            raise

    def stream_events(self, stop_event: threading.Event):
        yield from self._backend.iter_sse("/api/notifications/stream", stop_event)


# Backward-compatible alias
MongoNotificationService = NotificationService
