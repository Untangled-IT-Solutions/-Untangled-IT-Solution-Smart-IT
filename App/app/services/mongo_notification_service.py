"""Compatibility shim – notifications are Backend API only."""

from app.services.notification_service import NotificationService, MongoNotificationService

__all__ = ["NotificationService", "MongoNotificationService"]
