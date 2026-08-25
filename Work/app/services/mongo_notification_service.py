# app/services/mongo_notification_service.py
"""MongoDB Notification and activity service."""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.services.mongodb_service import MongoDBService


class MongoNotificationService:
    """Creates role-aware notifications and feeds the dashboard activity stream using MongoDB."""

    DIRECTOR_ROLE = "Director"

    def __init__(self, mongodb: MongoDBService) -> None:
        self._mongo = mongodb
        self._sound_enabled = True

    def _get_collection(self):
        """Get the notifications collection."""
        return self._mongo.get_collection("notifications")

    def _get_activity_collection(self):
        """Get the activity log collection."""
        return self._mongo.get_collection("activity_log")

    def _play_sound(self) -> None:
        """Play a notification sound."""
        if not self._sound_enabled:
            return
            
        try:
            import platform
            import subprocess
            
            system = platform.system()
            
            if system == "Windows":
                try:
                    import winsound
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
                except:
                    pass
            elif system == "Darwin":  # macOS
                try:
                    subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], capture_output=True)
                except:
                    pass
            else:  # Linux
                try:
                    subprocess.run(["aplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"], capture_output=True)
                except:
                    try:
                        subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"], capture_output=True)
                    except:
                        pass
        except:
            pass

    def notify_operational(
        self,
        recipient_roles: List[str],
        title: str,
        message: str,
        category: str,
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        """Notify operational roles, explicitly excluding the Director."""
        recipients = [
            role.strip()
            for role in recipient_roles
            if role and role.strip() and role.strip() != self.DIRECTOR_ROLE
        ]
        if not recipients:
            return

        collection = self._get_collection()
        now = datetime.now(timezone.utc)
        
        for role in recipients:
            notification = {
                "recipient_role": role,
                "title": title,
                "message": message,
                "category": category,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "is_executive": False,
                "is_read": False,
                "created_at": now,
                "updated_at": now
            }
            collection.insert_one(notification)
        
        self._play_sound()

    def notify_user(
        self,
        user_name: str,
        message: str,
        category: str = "General",
        title: str = "",
    ) -> None:
        """Send a notification to a specific user."""
        try:
            # Find the user by name
            employees_collection = self._mongo.get_collection("employees")
            employee = employees_collection.find_one({"full_name": user_name})
            
            if not employee:
                print(f"⚠️ User '{user_name}' not found in MongoDB")
                return
            
            # Get user role
            users_collection = self._mongo.get_collection("users")
            user = users_collection.find_one({"employee_id": employee["_id"]})
            
            role = user.get("role", "Staff") if user else "Staff"
            
            collection = self._get_collection()
            now = datetime.now(timezone.utc)
            
            notification = {
                "recipient_role": role,
                "recipient_name": user_name,
                "recipient_id": str(employee["_id"]),
                "title": title or category,
                "message": message,
                "category": category,
                "reference_type": "",
                "reference_id": "",
                "is_executive": False,
                "is_read": False,
                "created_at": now,
                "updated_at": now
            }
            collection.insert_one(notification)
            print(f"✅ Notification created for {user_name}")
            
            self._play_sound()
            
        except Exception as e:
            print(f"⚠️ Failed to send notification: {e}")

    def notify_executive(
        self,
        title: str,
        message: str,
        category: str,
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        """Send an executive brief to the Director only."""
        collection = self._get_collection()
        now = datetime.now(timezone.utc)
        
        notification = {
            "recipient_role": self.DIRECTOR_ROLE,
            "title": title,
            "message": message,
            "category": category,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "is_executive": True,
            "is_read": False,
            "created_at": now,
            "updated_at": now
        }
        collection.insert_one(notification)
        self._play_sound()

    def record_activity(
        self,
        category: str,
        description: str,
        reference_type: str = "",
        reference_id: str = "",
    ) -> None:
        """Record one source-neutral operational event for dashboards."""
        collection = self._get_activity_collection()
        now = datetime.now(timezone.utc)
        
        activity = {
            "category": category,
            "description": description,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "created_at": now
        }
        collection.insert_one(activity)

    def get_notifications(
        self,
        recipient_role: str = "All",
        unread_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Return notifications appropriate to the selected role view."""
        collection = self._get_collection()
        
        query = {}
        if recipient_role != "All":
            query["recipient_role"] = recipient_role
        if unread_only:
            query["is_read"] = False
            
        notifications = list(collection.find(query).sort("created_at", -1))
        
        # Convert ObjectId to string for JSON serialization
        for n in notifications:
            if "_id" in n:
                n["id"] = str(n["_id"])
                n["_id"] = str(n["_id"])
        
        return notifications

    def get_latest_activity(self, limit: int = 6) -> List[Dict[str, Any]]:
        """Return latest actions in reverse chronological order."""
        collection = self._get_activity_collection()
        activities = list(collection.find().sort("created_at", -1).limit(limit))
        
        for a in activities:
            if "_id" in a:
                a["id"] = str(a["_id"])
                a["_id"] = str(a["_id"])
        
        return activities

    def mark_read(self, notification_id: str) -> None:
        """Mark a notification as read."""
        collection = self._get_collection()
        collection.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"is_read": True, "updated_at": datetime.now(timezone.utc)}}
        )

    def count_unread(self, category: str | None = None) -> int:
        """Count unread notifications."""
        collection = self._get_collection()
        query = {"is_read": False}
        if category:
            query["category"] = category
        return collection.count_documents(query)

    def set_sound_enabled(self, enabled: bool) -> None:
        """Enable or disable notification sounds."""
        self._sound_enabled = enabled