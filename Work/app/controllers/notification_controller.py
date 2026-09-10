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

    def get_unread_count(self) -> int:
        """Get the number of unread notifications."""
        return self._notification_service.count_unread()

    def get_role_options(self) -> list:
        """Get available role filter options."""
        return self.ROLE_OPTIONS

    def notify_user(self, user_name: str, message: str, category: str = "General", title: str = "") -> None:
        """Send a notification to a specific user."""
        self._notification_service.notify_user(user_name, message, category, title)