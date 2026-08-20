# app/services/mongodb_service.py
"""MongoDB connection and management service."""

import secrets
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from app.utils.config import MONGO_URI, MONGO_DB_NAME


class MongoDBService:
    """Manages MongoDB connections and collections."""

    def __init__(
        self,
        uri: str = MONGO_URI,
        db_name: str = MONGO_DB_NAME,
    ) -> None:
        self._uri = uri
        self._db_name = db_name
        self._client: Optional[MongoClient] = None
        self._db: Optional[Any] = None
        self._connected = False
        
        self._connect()
        self._ensure_indexes()

    def _connect(self) -> None:
        """Establish connection to MongoDB."""
        try:
            self._client = MongoClient(self._uri)
            self._client.admin.command("ping")
            self._db = self._client[self._db_name]
            self._connected = True
            print(f"✅ Connected to MongoDB successfully")
            print(f"📊 Database: {self._db_name}")
            
            print("📁 Available databases:")
            for db in self._client.list_database_names():
                print(f"   - {db}")
                
            if self._db_name != "test":
                test_db = self._client["test"]
                if "quotes" in test_db.list_collection_names():
                    test_count = test_db["quotes"].count_documents({})
                    print(f"📋 Found {test_count} quotes in 'test' database")
                    
        except ConnectionFailure as e:
            self._connected = False
            print(f"❌ MongoDB connection failed: {e}")
            raise

    def _ensure_indexes(self) -> None:
        """Create necessary indexes for performance."""
        if not self._connected:
            return
            
        try:
            self._db.users.create_index("username", unique=True)
            self._db.users.create_index("email", unique=True)
            self._db.users.create_index("employee_id", unique=True, sparse=True)
            self._db.users.create_index("status")
            self._db.users.create_index("role")
            
            self._db.employees.create_index("employee_number", unique=True)
            self._db.employees.create_index("email", unique=True, sparse=True)
            self._db.employees.create_index("full_name")
            self._db.employees.create_index("department")
            self._db.employees.create_index("status")
            
            self._db.attendance.create_index([("employee_id", ASCENDING), ("work_date", ASCENDING)], unique=True)
            self._db.attendance.create_index("status")
            self._db.attendance.create_index("work_date")
            
            self._db.daily_activities.create_index([("employee_id", ASCENDING), ("date", ASCENDING)], unique=True)
            self._db.daily_activities.create_index("date")
            
            self._db.work_assignments.create_index("employee_id")
            self._db.work_assignments.create_index("status")
            self._db.work_assignments.create_index("due_date")
            self._db.work_assignments.create_index("priority")
            self._db.work_assignments.create_index("category")
            self._db.work_assignments.create_index("assigned_employee")
            
            self._db.auth_sessions.create_index("token", unique=True)
            self._db.auth_sessions.create_index("user_id")
            self._db.auth_sessions.create_index("login_at")
            
            if "quotes" in self._db.list_collection_names():
                self._db.quotes.create_index("reference", unique=True)
                self._db.quotes.create_index("status")
                self._db.quotes.create_index("createdAt")
            
            try:
                if "work_assignments" in self._db.list_collection_names():
                    self._db.work_assignments.create_index(
                        [("title", TEXT), ("description", TEXT), ("employee_name", TEXT)],
                        default_language="english"
                    )
            except Exception:
                pass
            
            print("✅ MongoDB indexes created")
        except Exception as e:
            print(f"⚠️ MongoDB index creation warning: {e}")

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def db(self) -> Any:
        if not self._connected:
            self._connect()
        return self._db

    def get_collection(self, name: str) -> Any:
        return self.db[name]

    def get_collection_from_db(self, db_name: str, collection_name: str) -> Any:
        if not self._connected:
            self._connect()
        db = self._client[db_name]
        return db[collection_name]

    def get_quotes(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get quotes from MongoDB."""
        if not self._connected:
            return []
        try:
            collection = self.get_collection("quotes")
            quotes = list(collection.find().sort("createdAt", -1).limit(limit))
            
            if not quotes and self._db_name != "test":
                print("🔄 No quotes in current database, checking 'test' database...")
                test_collection = self.get_collection_from_db("test", "quotes")
                quotes = list(test_collection.find().sort("createdAt", -1).limit(limit))
                if quotes:
                    print(f"✅ Found {len(quotes)} quotes in 'test' database")
                
            return quotes
        except Exception as e:
            print(f"Error getting quotes: {e}")
            return []

    def update_quote_status(self, reference: str, status: str) -> bool:
        """Update quote status in MongoDB."""
        if not self._connected:
            return False
        try:
            collection = self.get_collection("quotes")
            result = collection.update_one(
                {"reference": reference},
                {"$set": {"status": status, "updatedAt": datetime.now(timezone.utc)}}
            )
            
            if result.matched_count == 0 and self._db_name != "test":
                test_collection = self.get_collection_from_db("test", "quotes")
                result = test_collection.update_one(
                    {"reference": reference},
                    {"$set": {"status": status, "updatedAt": datetime.now(timezone.utc)}}
                )
                
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            print(f"Error updating quote status: {e}")
            return False

    def update_quote_reply(self, reference: str, reply: str) -> bool:
        """Update quote reply in MongoDB."""
        if not self._connected:
            return False
        try:
            collection = self.get_collection("quotes")
            result = collection.update_one(
                {"reference": reference},
                {"$set": {"replyMessage": reply, "repliedAt": datetime.now(timezone.utc)}}
            )
            
            if result.matched_count == 0 and self._db_name != "test":
                test_collection = self.get_collection_from_db("test", "quotes")
                result = test_collection.update_one(
                    {"reference": reference},
                    {"$set": {"replyMessage": reply, "repliedAt": datetime.now(timezone.utc)}}
                )
                
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            print(f"Error updating quote reply: {e}")
            return False

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._connected = False

    def ping(self) -> bool:
        try:
            self.db.command("ping")
            return True
        except:
            return False

    @staticmethod
    def get_session_token() -> str:
        return secrets.token_urlsafe(64)