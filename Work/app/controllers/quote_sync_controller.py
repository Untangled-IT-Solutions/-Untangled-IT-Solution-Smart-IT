# app/controllers/quote_sync_controller.py
"""Quote Sync controller - MongoDB only."""

from app.services.mongodb_service import MongoDBService


class QuoteSyncController:
    """Controls quote synchronization from MongoDB."""

    def __init__(self, mongodb_service: MongoDBService) -> None:
        self._mongodb = mongodb_service

    def sync_quotes(self) -> dict:
        """Sync quotes from MongoDB (already in MongoDB, just refresh)."""
        try:
            collection = self._mongodb.get_collection("quotes")
            count = collection.count_documents({})
            return {
                "synced": count,
                "status": "success",
                "message": f"Found {count} quotes in MongoDB"
            }
        except Exception as e:
            return {
                "synced": 0,
                "status": "error",
                "message": str(e)
            }

    def get_sync_status(self) -> dict:
        """Get the current sync status."""
        try:
            collection = self._mongodb.get_collection("quotes")
            count = collection.count_documents({})
            return {
                "total_quotes": count,
                "status": "connected" if self._mongodb.is_connected else "disconnected"
            }
        except Exception as e:
            return {
                "total_quotes": 0,
                "status": "error",
                "error": str(e)
            }