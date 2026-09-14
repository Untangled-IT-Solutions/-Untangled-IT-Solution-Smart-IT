"""Notifications – Backend API only (robust mark-as-read)."""
from __future__ import annotations

from typing import Any, List, Optional

from app.models.notification import Notification
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class NotificationService:
    """Backend-backed notification surface."""

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    @staticmethod
    def _parse_is_read(raw: dict) -> bool:
        """Treat missing read flags as unread. Support legacy field names."""
        for key in ("is_read", "read", "isRead", "seen", "is_seen"):
            if key not in raw:
                continue
            val = raw.get(key)
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return bool(val)
            s = str(val).strip().lower()
            if s in ("true", "1", "yes", "read", "seen"):
                return True
            if s in ("false", "0", "no", "unread", "new", ""):
                return False
        status = str(raw.get("status") or "").strip().lower()
        if status in ("read", "seen", "archived", "done"):
            return True
        if status in ("unread", "new", "pending", "open"):
            return False
        return False  # default: unread

    def _to_model(self, raw: dict) -> Notification:
        nid = raw.get("id") or raw.get("_id")
        if nid is not None:
            nid = str(nid)
        return Notification(
            id=nid,
            recipient_role=str(raw.get("recipient_role") or raw.get("role") or "All"),
            title=str(raw.get("title") or ""),
            message=str(raw.get("message") or raw.get("body") or ""),
            category=str(raw.get("category") or "General"),
            reference_type=str(raw.get("reference_type") or ""),
            reference_id=raw.get("reference_id"),
            is_executive=bool(raw.get("is_executive")),
            is_read=self._parse_is_read(raw),
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
            result.sort(key=lambda n: n.created_at or "", reverse=True)
            return result
        except BackendAPIError as exc:
            print(f"⚠️ notifications fetch failed: {exc}")
            return []

    def mark_read(self, notification_id: str) -> bool:
        """Mark a single notification as read. Tries several common API shapes."""
        if not notification_id:
            print("⚠️ mark_read: empty id")
            return False

        nid = str(notification_id).strip()
        print(f"📋 Marking notification as read: {nid}")

        # Prefer the routes the live backend actually implements first
        attempts = [
            ("POST",  f"/api/notifications/{nid}/read", None),
            ("PATCH", f"/api/notifications/{nid}/read", None),
            ("PUT",   f"/api/notifications/{nid}/read", None),
            ("PATCH", f"/api/notifications/{nid}", {"is_read": True, "read": True, "isRead": True}),
            ("PUT",   f"/api/notifications/{nid}", {"is_read": True, "read": True, "isRead": True}),
            ("POST",  f"/api/notifications/read", {"id": nid, "notification_id": nid}),
            ("POST",  f"/api/notifications/mark-read", {"id": nid, "notification_id": nid}),
        ]

        last_error = None
        for method, path, payload in attempts:
            try:
                data = self._backend.request(method, path, payload)
                # Treat explicit matched/modified=0 as failure so we can try next shape
                if isinstance(data, dict):
                    matched = data.get("matched")
                    modified = data.get("modified") or data.get("count")
                    if matched is not None and int(matched) == 0:
                        print(f"⚠️ {method} {path} matched 0 docs – trying next")
                        continue
                    if modified is not None and int(modified) == 0 and matched is None:
                        # some backends only return modified
                        pass
                print(f"✅ Notification {nid} marked as read via {method} {path}")
                return True
            except BackendAPIError as exc:
                last_error = exc
                continue

        print(f"⚠️ mark_read failed for {nid}: {last_error}")
        return False

    def mark_all_read(self, role: str = "All") -> int:
        """Mark all unread notifications as read. Returns how many were marked."""
        print(f"📋 mark_all_read(role={role})")
        payload = {"role": role} if role and role != "All" else {}

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
                    data.get("modified")
                    or data.get("count")
                    or data.get("updated")
                    or data.get("nModified")
                    or 0
                )
                if count > 0 or data.get("success") is True:
                    # If backend says success but count is 0, still try per-item below
                    if count > 0:
                        print(f"✅ mark_all_read via {method} {path} → {count}")
                        return count
            except BackendAPIError as exc:
                print(f"⚠️ {method} {path} failed: {exc}")
                continue

        # Fallback: mark each unread notification individually
        items = self.get_notifications(role=role, unread_only=True) or []
        updated = 0
        for n in items:
            nid = str(n.id) if n.id is not None else ""
            if not nid:
                continue
            if self.mark_read(nid):
                updated += 1
        print(f"✅ mark_all_read fallback marked {updated}/{len(items)}")
        return updated


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
        """Prefer dedicated unread-count endpoint (fast); fall back to list."""
        try:
            data = self._backend.request("GET", "/api/notifications/unread-count")
            if isinstance(data, dict):
                for key in ("count", "unread", "unread_count"):
                    if key in data and data[key] is not None:
                        return int(data[key])
        except Exception as exc:
            print(f"⚠️ unread-count endpoint failed: {exc}")
        try:
            items = self.get_notifications(role=role, unread_only=True)
            return len(items or [])
        except Exception:
            try:
                return len([n for n in self.get_notifications(role=role) if not n.is_read])
            except Exception:
                return 0


# Backward-compatible alias
MongoNotificationService = NotificationService