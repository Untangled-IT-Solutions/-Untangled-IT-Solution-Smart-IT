# app/controllers/notification_controller.py
"""Notification controller."""

from app.services.mongo_notification_service import MongoNotificationService
from app.services.mongo_auth_service import MongoAuthService


class NotificationController:
    """Controls notification display and filtering."""

    ROLE_OPTIONS = ["All", "Director", "Branch Manager", "Business Lead", "Operations Manager", "Staff", "Intern"]

    def __init__(
        self,
        notification_service: MongoNotificationService,
        auth_service: MongoAuthService,
    ) -> None:
        self._notification_service = notification_service
        self._auth_service = auth_service

    def get_notifications(self, role: str = "All", unread_only: bool = False) -> list:
        """Get notifications filtered by role and read status."""
        return self._notification_service.get_notifications(role, unread_only)

    def mark_read(self, notification_id: str) -> None:
        """Mark a notification as read."""
        self._notification_service.mark_read(notification_id)

    def mark_all_read(self, role: str = "All") -> int:
        """Mark all unread notifications as read (optionally filtered by role)."""
        try:
            if hasattr(self._notification_service, "mark_all_read"):
                return int(self._notification_service.mark_all_read(role) or 0)
            # Fallback: mark one by one
            items = self.get_notifications(role=role, unread_only=True)
            count = 0
            for item in items or []:
                nid = None
                if isinstance(item, dict):
                    nid = item.get("id") or item.get("_id")
                else:
                    nid = getattr(item, "id", None)
                if nid is not None:
                    self.mark_read(str(nid))
                    count += 1
            return count
        except Exception as e:
            print(f"⚠️ mark_all_read failed: {e}")
            return 0

    def get_unread_count(self) -> int:
        """Get the number of unread notifications."""
        return self._notification_service.count_unread()

    def get_role_options(self) -> list:
        """Get available role filter options."""
        return self.ROLE_OPTIONS

    def notify_user(
        self,
        user_name: str,
        message: str,
        category: str = "General",
        title: str = "",
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        """Send a notification to a specific user (extends existing service method)."""
        try:
            self._notification_service.notify_user(
                user_name,
                message,
                category,
                title,
                reference_type=reference_type,
                reference_id=reference_id,
            )
        except Exception as e:
            # Never fail the caller (e.g. quote assignment) because of notifications
            print(f"⚠️ notify_user failed: {e}")

    def notify_executive(
        self,
        title: str,
        message: str,
        category: str = "Quote",
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        """Send a Director-only notification via the existing service."""
        try:
            self._notification_service.notify_executive(
                title,
                message,
                category,
                reference_type=reference_type,
                reference_id=reference_id,
            )
        except Exception as e:
            print(f"⚠️ notify_executive failed: {e}")

    def notify_operational(
        self,
        recipient_roles: list,
        title: str,
        message: str,
        category: str,
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        """Passthrough to existing operational notifications."""
        try:
            self._notification_service.notify_operational(
                recipient_roles,
                title,
                message,
                category,
                reference_type=reference_type,
                reference_id=reference_id,
            )
        except Exception as e:
            print(f"⚠️ notify_operational failed: {e}")