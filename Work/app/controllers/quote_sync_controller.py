# app/controllers/quote_sync_controller.py
"""Quote Sync Controller."""

from typing import Dict, Any, Optional
from app.services.quote_sync_service import QuoteSyncService
from app.services.mongodb_service import MongoDBService
from app.services.auth_service import AuthService


class QuoteSyncController:
    """Controller for quote synchronization."""

    def __init__(
        self,
        quote_sync_service: QuoteSyncService,
        mongodb_service: MongoDBService,
        auth_service: AuthService,
    ):
        self._quote_sync_service = quote_sync_service
        self._mongodb_service = mongodb_service
        self._auth_service = auth_service

    def is_mongodb_connected(self) -> bool:
        if self._mongodb_service:
            return self._mongodb_service.is_connected
        return False

    def sync_quotes_from_mongodb(self) -> Dict[str, Any]:
        if not self.is_mongodb_connected():
            return {"success": False, "message": "MongoDB not connected"}
        
        try:
            result = self._quote_sync_service.sync_quotes_from_mongodb()
            return result
        except Exception as e:
            return {"success": False, "message": str(e)}

    def sync_all_to_mongodb(self) -> Dict[str, Any]:
        if not self.is_mongodb_connected():
            return {"success": False, "message": "MongoDB not connected"}
        
        try:
            result = self._quote_sync_service.sync_all_to_mongodb()
            return result
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_sync_status(self) -> Dict[str, Any]:
        return {
            "mongodb_connected": self.is_mongodb_connected(),
            "last_sync": self._quote_sync_service.get_last_sync_time() if self._quote_sync_service else None,
            "statistics": self._quote_sync_service.get_quote_statistics() if self._quote_sync_service else {},
        }