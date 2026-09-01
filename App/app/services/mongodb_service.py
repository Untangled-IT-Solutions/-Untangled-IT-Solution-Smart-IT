# app/services/mongodb_service.py
"""MongoDB connection and management service."""

from datetime import datetime, timezone
from typing import Optional, Any, List, Dict

from pymongo import (
    MongoClient,
    ASCENDING,
    DESCENDING,
    TEXT,
)
from pymongo.errors import ConnectionFailure

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

    # ==================================================================
    # CONNECTION
    # ==================================================================

    def _connect(self) -> None:
        """Establish connection to MongoDB."""

        try:
            self._client = MongoClient(
                self._uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=15000,
                maxPoolSize=20,
                minPoolSize=1,
                retryWrites=True,
            )

            self._client.admin.command("ping")

            self._db = self._client[self._db_name]
            self._connected = True

            print("✅ MongoDB connected successfully")
            print(f"📊 Database: {self._db_name}")

            # Avoid list_database_names()/count_documents() diagnostics during
            # application startup. They add network round-trips before the UI
            # can become usable and provide little value in production.
        except ConnectionFailure as exc:

            self._connected = False

            print(
                f"❌ MongoDB connection failed: {exc}"
            )

            raise

        except Exception as exc:

            self._connected = False

            print(
                f"❌ MongoDB initialization failed: {exc}"
            )

            raise

    # ==================================================================
    # INDEXES
    # ==================================================================

    def _ensure_indexes(self) -> None:
        """Create necessary MongoDB indexes."""

        if not self._connected or self._db is None:
            return

        try:

            # ----------------------------------------------------------
            # Users
            # ----------------------------------------------------------

            # IMPORTANT:
            # Existing production database already contains:
            #
            # username_1:
            #   unique=True
            #   sparse=True
            #
            # Keep the definition identical so MongoDB does not raise
            # IndexKeySpecsConflict.
            self._db.users.create_index(
                "username",
                unique=True,
                sparse=True,
            )

            self._db.users.create_index(
                "email",
                unique=True,
                sparse=True,
            )

            self._db.users.create_index(
                "employee_id",
                unique=True,
                sparse=True,
            )

            self._db.users.create_index("status")
            self._db.users.create_index("role")

            # ----------------------------------------------------------
            # Employees
            # ----------------------------------------------------------

            self._db.employees.create_index(
                "employee_number",
                unique=True,
            )

            self._db.employees.create_index(
                "email",
                unique=True,
                sparse=True,
            )

            self._db.employees.create_index("full_name")
            self._db.employees.create_index("department")
            self._db.employees.create_index("status")

            # ----------------------------------------------------------
            # Attendance
            # ----------------------------------------------------------

            self._db.attendance.create_index(
                [
                    ("employee_id", ASCENDING),
                    ("work_date", ASCENDING),
                ],
                unique=True,
            )

            self._db.attendance.create_index("status")
            self._db.attendance.create_index("work_date")

            # ----------------------------------------------------------
            # Daily activities
            # ----------------------------------------------------------

            self._db.daily_activities.create_index(
                [
                    ("employee_id", ASCENDING),
                    ("date", ASCENDING),
                ],
                unique=True,
            )

            self._db.daily_activities.create_index("date")

            # ----------------------------------------------------------
            # Work assignments
            # ----------------------------------------------------------

            self._db.work_assignments.create_index(
                "employee_id"
            )

            self._db.work_assignments.create_index(
                "status"
            )

            self._db.work_assignments.create_index(
                "due_date"
            )

            self._db.work_assignments.create_index(
                "priority"
            )

            self._db.work_assignments.create_index(
                "category"
            )

            self._db.work_assignments.create_index(
                "assigned_employee"
            )

            # ----------------------------------------------------------
            # Auth sessions
            # ----------------------------------------------------------

            self._db.auth_sessions.create_index(
                "token",
                unique=True,
            )

            self._db.auth_sessions.create_index(
                "user_id"
            )

            self._db.auth_sessions.create_index(
                "login_at"
            )

            # ----------------------------------------------------------
            # Quotes
            # ----------------------------------------------------------

            try:

                self._db.quotes.create_index(
                    "reference",
                    unique=True,
                )

                self._db.quotes.create_index(
                    "status"
                )

                self._db.quotes.create_index(
                    "createdAt"
                )

            except Exception as exc:

                print(
                    f"⚠️ Quotes index warning: {exc}"
                )

            # ----------------------------------------------------------
            # Orders
            # ----------------------------------------------------------

            try:

                self._db.orders.create_index(
                    "reference",
                    unique=True,
                )

                self._db.orders.create_index(
                    "status"
                )

                self._db.orders.create_index(
                    "createdAt"
                )

                self._db.orders.create_index(
                    "updatedAt"
                )

                self._db.orders.create_index(
                    "customerName"
                )

                self._db.orders.create_index(
                    "company"
                )

                self._db.orders.create_index(
                    "email"
                )

                self._db.orders.create_index(
                    "phone"
                )

                self._db.orders.create_index(
                    "assigned_to.username"
                )

                self._db.orders.create_index(
                    "assignedTo.username"
                )

            except Exception as exc:

                print(
                    f"⚠️ Orders index warning: {exc}"
                )

            # ----------------------------------------------------------
            # Work assignment text search
            # ----------------------------------------------------------

            try:

                self._db.work_assignments.create_index(
                    [
                        ("title", TEXT),
                        ("description", TEXT),
                        ("employee_name", TEXT),
                    ],
                    default_language="english",
                )

            except Exception as exc:

                # A text index may already exist. Do not allow an
                # optional search index to prevent application startup.
                print(
                    f"⚠️ Work assignment text index warning: {exc}"
                )

            print("✅ MongoDB indexes created")

        except Exception as exc:

            print(
                f"⚠️ MongoDB index creation warning: {exc}"
            )

    # ==================================================================
    # PROPERTIES
    # ==================================================================

    @property
    def connected(self) -> bool:
        """Return whether MongoDB is currently connected."""

        return self._connected

    @property
    def is_connected(self) -> bool:
        """Compatibility alias for connected."""

        return self._connected

    @property
    def db(self) -> Any:
        """
        Return the configured PyMongo Database object.

        IMPORTANT:
            This returns a pymongo.database.Database.

        It should NOT be treated as a MongoDBService instance.
        """

        if not self._connected:
            self._connect()

        if self._db is None:
            raise RuntimeError(
                "MongoDB database is unavailable."
            )

        return self._db

    @property
    def database(self) -> Any:
        """
        Compatibility alias for the configured PyMongo Database.

        This makes the distinction between the service and database
        object explicit.
        """

        return self.db

    @property
    def client(self) -> Optional[MongoClient]:
        """Return the underlying MongoClient."""

        return self._client

    @property
    def db_name(self) -> str:
        """Return the configured database name."""

        return self._db_name

    # ==================================================================
    # COLLECTION ACCESS
    # ==================================================================

    def get_collection(
        self,
        name: str,
    ) -> Any:
        """Return a collection from the configured database."""

        if not name:
            raise ValueError(
                "Collection name cannot be empty."
            )

        return self.db[name]

    def get_collection_from_db(
        self,
        db_name: str,
        collection_name: str,
    ) -> Any:
        """Return a collection from a specific database."""

        if not db_name:
            raise ValueError(
                "Database name cannot be empty."
            )

        if not collection_name:
            raise ValueError(
                "Collection name cannot be empty."
            )

        if not self._connected:
            self._connect()

        if self._client is None:
            raise RuntimeError(
                "MongoDB client is unavailable."
            )

        database = self._client[db_name]

        return database[collection_name]

    # ==================================================================
    # QUOTES
    # ==================================================================

    def get_quotes(
        self,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Get quotes from MongoDB."""

        if not self._connected:
            return []

        try:

            collection = self.get_collection(
                "quotes"
            )

            quotes = list(
                collection.find()
                .sort(
                    "createdAt",
                    DESCENDING,
                )
                .limit(limit)
            )

            # ----------------------------------------------------------
            # Test database fallback
            # ----------------------------------------------------------

            if (
                not quotes
                and self._db_name != "test"
            ):

                print(
                    "🔄 No quotes in current database, "
                    "checking 'test' database..."
                )

                test_collection = (
                    self.get_collection_from_db(
                        "test",
                        "quotes",
                    )
                )

                quotes = list(
                    test_collection.find()
                    .sort(
                        "createdAt",
                        DESCENDING,
                    )
                    .limit(limit)
                )

                if quotes:
                    print(
                        f"✅ Found {len(quotes)} quotes "
                        f"in 'test' database"
                    )

            return quotes

        except Exception as exc:

            print(
                f"❌ Error getting quotes: {exc}"
            )

            return []

    # ==================================================================
    # ORDERS
    # ==================================================================

    def get_orders(
        self,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Get orders from MongoDB.

        First searches the configured application database.

        If no orders are found and the configured database is not
        'test', the method also checks test.orders.
        """

        if not self._connected:

            print(
                "⚠️ get_orders(): MongoDB is not connected"
            )

            return []

        try:

            # ----------------------------------------------------------
            # Current configured database
            # ----------------------------------------------------------

            collection = self.get_collection(
                "orders"
            )

            orders = list(
                collection.find()
                .sort(
                    "createdAt",
                    DESCENDING,
                )
                .limit(limit)
            )

            print(
                f"🔎 Orders in "
                f"'{self._db_name}.orders': "
                f"{len(orders)}"
            )

            if orders:
                return orders

            # ----------------------------------------------------------
            # Test database fallback
            # ----------------------------------------------------------

            if self._db_name != "test":

                print(
                    "🔄 No orders in current database, "
                    "checking 'test.orders'..."
                )

                try:

                    test_collection = (
                        self.get_collection_from_db(
                            "test",
                            "orders",
                        )
                    )

                    orders = list(
                        test_collection.find()
                        .sort(
                            "createdAt",
                            DESCENDING,
                        )
                        .limit(limit)
                    )

                    print(
                        f"🔎 Orders in 'test.orders': "
                        f"{len(orders)}"
                    )

                    if orders:

                        print(
                            f"✅ Found {len(orders)} orders "
                            f"in 'test' database"
                        )

                        return orders

                except Exception as exc:

                    print(
                        f"⚠️ Could not read "
                        f"test.orders: {exc}"
                    )

            print(
                "ℹ️ No orders found in MongoDB."
            )

            return []

        except Exception as exc:

            print(
                f"❌ Error getting orders: {exc}"
            )

            return []

    def get_order(
        self,
        reference: str,
    ) -> Optional[Dict[str, Any]]:
        """Get one order by its public reference."""

        if (
            not self._connected
            or not reference
        ):
            return None

        try:

            collection = self.get_collection(
                "orders"
            )

            order = collection.find_one(
                {"reference": reference}
            )

            if order:
                return order

            # ----------------------------------------------------------
            # Test database fallback
            # ----------------------------------------------------------

            if self._db_name != "test":

                test_collection = (
                    self.get_collection_from_db(
                        "test",
                        "orders",
                    )
                )

                return test_collection.find_one(
                    {"reference": reference}
                )

            return None

        except Exception as exc:

            print(
                f"❌ Error getting order "
                f"{reference}: {exc}"
            )

            return None

    def update_order_status(
        self,
        reference: str,
        status: str,
    ) -> bool:
        """
        Update an order status.

        Uses the actual orders schema:
            updatedAt
        """

        if (
            not self._connected
            or not reference
        ):
            return False

        try:

            now = datetime.now(timezone.utc)

            collection = self.get_collection(
                "orders"
            )

            result = collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "status": status,
                        "updatedAt": now,
                    }
                },
            )

            if result.matched_count:
                return True

            # ----------------------------------------------------------
            # Test database fallback
            # ----------------------------------------------------------

            if self._db_name != "test":

                test_collection = (
                    self.get_collection_from_db(
                        "test",
                        "orders",
                    )
                )

                result = test_collection.update_one(
                    {"reference": reference},
                    {
                        "$set": {
                            "status": status,
                            "updatedAt": now,
                        }
                    },
                )

                return result.matched_count > 0

            return False

        except Exception as exc:

            print(
                f"❌ Error updating order status: {exc}"
            )

            return False

    def update_order_assignment(
        self,
        reference: str,
        assignment: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Assign or unassign an order.

        Supports:
            assignedTo
            assigned_to
        """

        if (
            not self._connected
            or not reference
        ):
            return False

        try:

            now = datetime.now(timezone.utc)

            collection = self.get_collection(
                "orders"
            )

            if assignment:

                update = {
                    "$set": {
                        "assignedTo": assignment,
                        "updatedAt": now,
                    }
                }

            else:

                update = {
                    "$unset": {
                        "assignedTo": "",
                        "assigned_to": "",
                    },
                    "$set": {
                        "updatedAt": now,
                    },
                }

            result = collection.update_one(
                {"reference": reference},
                update,
            )

            if result.matched_count:
                return True

            # ----------------------------------------------------------
            # Test database fallback
            # ----------------------------------------------------------

            if self._db_name != "test":

                test_collection = (
                    self.get_collection_from_db(
                        "test",
                        "orders",
                    )
                )

                result = test_collection.update_one(
                    {"reference": reference},
                    update,
                )

                return result.matched_count > 0

            return False

        except Exception as exc:

            print(
                f"❌ Error updating order assignment: {exc}"
            )

            return False

    # ==================================================================
    # GENERIC HELPERS
    # ==================================================================

    def insert_one(
        self,
        collection_name: str,
        document: Dict[str, Any],
    ) -> Any:
        """Insert one document."""

        return self.get_collection(
            collection_name
        ).insert_one(document)

    def update_one(
        self,
        collection_name: str,
        filter_query: Dict[str, Any],
        update: Dict[str, Any],
    ) -> Any:
        """Update one document."""

        return self.get_collection(
            collection_name
        ).update_one(
            filter_query,
            update,
        )

    def find_one(
        self,
        collection_name: str,
        filter_query: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Find one document."""

        return self.get_collection(
            collection_name
        ).find_one(filter_query)

    def find_many(
        self,
        collection_name: str,
        filter_query: Optional[
            Dict[str, Any]
        ] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Find many documents."""

        query = filter_query or {}

        return list(
            self.get_collection(
                collection_name
            )
            .find(query)
            .limit(limit)
        )

    def delete_one(
        self,
        collection_name: str,
        filter_query: Dict[str, Any],
    ) -> Any:
        """Delete one document."""

        return self.get_collection(
            collection_name
        ).delete_one(filter_query)

    # ==================================================================
    # CLOSE
    # ==================================================================

    def close(self) -> None:
        """Close MongoDB connection."""

        try:

            if self._client is not None:
                self._client.close()

            self._connected = False
            self._client = None
            self._db = None

            print(
                "🔌 MongoDB connection closed"
            )

        except Exception as exc:

            print(
                f"⚠️ MongoDB close warning: {exc}"
            )