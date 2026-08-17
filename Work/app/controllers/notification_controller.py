"""Notification centre controller."""

from app.models.notification import Notification
from app.services.notification_service import NotificationService


class NotificationController:
    """Supplies role-filtered notifications to the notification view."""

    ROLE_OPTIONS = (
        "All",
        "Operations Manager",
        "Business Lead",
        "Director",
        "Senior Technician",
        "RFQ Administrator",
        "Marketing & RFQ Support",
        "Software Engineer",
        "Technical Support Intern",
    )

    def __init__(self, notification_service: NotificationService) -> None:
        self._notification_service = notification_service

    def get_notifications(self, role: str = "All", unread_only: bool = False) -> list[Notification]:
        return self._notification_service.get_notifications(role, unread_only)

    def mark_read(self, notification_id: int) -> None:
        self._notification_service.mark_read(notification_id)
