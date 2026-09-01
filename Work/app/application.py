"""Application bootstrap and dependency wiring with MongoDB employee data."""

import customtkinter as ctk
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path if needed
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.controllers.app_controller import AppController
from app.database.database import Database
from app.utils.theme import Theme

# SQLite services still used by other parts of the application
from app.services.auth_service import AuthService
from app.services.approval_service import ApprovalService
from app.services.attendance_service import AttendanceService
from app.services.office_request_service import OfficeRequestService
from app.services.backend_people_service import BackendPeopleService
from app.services.backend_work_service import BackendWorkService
from app.services.backend_calendar_service import BackendCalendarService
from app.services.backend_hr_service import BackendHRService
from app.services.project_service import ProjectService
from app.services.report_service import ReportService
from app.services.search_service import SearchService
from app.services.work_service import WorkService
from app.services.notification_service import NotificationService
from app.services.backend_api_client import BackendAPIClient
from app.services.backend_dashboard_service import BackendDashboardService

# MongoDB services
from app.services.mongo_auth_service import MongoAuthService
from app.services.mongo_attendance_service import MongoAttendanceService


class Application:
    """Composition root for Untangled Nexus."""


    def __init__(self):
        self._init_ui()

        print("\n" + "=" * 60)
        print("🚀 UNTANGLED NEXUS - Application Initialization")
        print("=" * 60)

        # =========================================================
        # SQLite
        # =========================================================
        #
        # SQLite is still initialized because some existing
        # services in the application still depend on it.
        #
        # IMPORTANT:
        # Employee/People data is now read from MongoDB.
        # =========================================================

        print("\n📁 Initializing SQLite Database...")

        self.database = Database()
        self.database.initialize()

        print("✅ SQLite Database ready")

        # =========================================================
        # Backend API
        # =========================================================
        # The distributed EXE never connects directly to MongoDB.
        # MongoDB credentials remain on the backend server.
        # =========================================================
        print("\n🌐 Connecting to Backend API...")
        self.backend_api = BackendAPIClient()
        print("✅ Backend API configured")

        # Remote authentication and attendance adapters.
        self.mongo_auth = MongoAuthService(self.backend_api)
        self.mongo_attendance = MongoAttendanceService(self.backend_api)
        self.mongo_notification = NotificationService(self.database)

        # =========================================================
        # Services
        # =========================================================

        print("\n📦 Initializing services...")

        # ---------------------------------------------------------
        # Authentication
        # ---------------------------------------------------------

        self.auth_service = AuthService(
            self.database
        )

        # ---------------------------------------------------------
        # PEOPLE SERVICE
        #
        # IMPORTANT:
        # This now uses MongoDB.
        # ---------------------------------------------------------

        self.people_service = BackendPeopleService(
            self.backend_api
        )

        # ---------------------------------------------------------
        # Work
        # ---------------------------------------------------------

        self.work_service = BackendWorkService(
            self.backend_api
        )

        # ---------------------------------------------------------
        # Attendance
        # ---------------------------------------------------------

        self.attendance_service = AttendanceService(
            self.database,
            self.mongo_notification,
        )

        # ---------------------------------------------------------
        # Calendar
        # ---------------------------------------------------------

        self.calendar_service = BackendCalendarService(
            self.backend_api
        )

        self.hr_service = BackendHRService(
            self.backend_api
        )

        # ---------------------------------------------------------
        # Approvals
        # ---------------------------------------------------------

        self.approval_service = ApprovalService(
            self.database,
            self.mongo_notification,
        )

        # ---------------------------------------------------------
        # Office Requests
        # ---------------------------------------------------------

        self.office_request_service = OfficeRequestService(
            self.database,
            self.approval_service,
            self.mongo_notification,
        )

        # ---------------------------------------------------------
        # Projects
        # ---------------------------------------------------------

        self.project_service = ProjectService(
            self.database
        )

        # ---------------------------------------------------------
        # Reports
        # ---------------------------------------------------------

        self.report_service = ReportService(
            self.database
        )

        # ---------------------------------------------------------
        # Search
        # ---------------------------------------------------------

        self.search_service = SearchService(
            self.database
        )

        # Dashboard is backend/API sourced. The desktop never connects directly to MongoDB.
        self.dashboard_service = BackendDashboardService(self.backend_api)

        self.quote_sync_service = None

        # =========================================================
        # Application Controller
        # =========================================================

        print("\n🎮 Initializing application controller...")

        self.controller = AppController(
            auth_service=self.auth_service,
            dashboard_service=self.dashboard_service,
            people_service=self.people_service,
            work_service=self.work_service,
            attendance_service=self.attendance_service,
            calendar_service=self.calendar_service,
            approval_service=self.approval_service,
            office_request_service=self.office_request_service,
            notification_service=self.mongo_notification,
            search_service=self.search_service,
            project_service=self.project_service,
            report_service=self.report_service,
            database=self.database,
            mongodb_service=None,
            quote_sync_service=self.quote_sync_service,
            mongo_auth_service=self.mongo_auth,
            mongo_attendance_service=self.mongo_attendance,
            backend_api=self.backend_api,
            hr_service=self.hr_service,
        )

        # =========================================================
        # Initialization complete
        # =========================================================

        print("\n" + "=" * 60)
        print("✅ APPLICATION INITIALIZATION COMPLETE")
        print("=" * 60)

        print("\n💡 System Status:")

        print("   🌐 Backend API: ✅")
        print("   🔐 Authentication: Backend API")
        print("   ⏱️ Attendance: Backend API")
        print("=" * 60)

    # =============================================================
    # UI INITIALIZATION
    # =============================================================

    def _init_ui(self):
        """Initialize the CustomTkinter environment."""

        self._temp_root = ctk.CTk()

        self._temp_root.withdraw()

        Theme.apply_mode()

        ctk.set_default_color_theme(
            "dark-blue"
        )

    # =============================================================
    # DEMO ACCOUNT
    # =============================================================

    def _ensure_demo_account_only(self):
        """
        Ensure the demo employee and demo user exist.

        This does NOT synchronize employees from SQLite.
        MongoDB remains the source of truth for employees.
        """

        employees = self.mongodb.get_collection(
            "employees"
        )

        users = self.mongodb.get_collection(
            "users"
        )

        print("\n🔑 Checking demo account...")

        # ---------------------------------------------------------
        # Demo employee
        # ---------------------------------------------------------

        employee = employees.find_one(
            {
                "email": self.DEMO_USERNAME
            }
        )

        if employee is None:

            print("📝 Creating demo employee...")

            employee = {
                "employee_number": "DEMO-001",
                "first_name": "Demo",
                "last_name": "Admin",
                "full_name": self.DEMO_FULL_NAME,
                "position": "Director",
                "department": "Administration",
                "role": "Director",
                "email": self.DEMO_USERNAME,
                "status": "Active",
                "employment_type": "Full-time",
                "date_joined": datetime.now().isoformat(),
                "clocked_in": False,
            }

            result = employees.insert_one(
                employee
            )

            employee["_id"] = result.inserted_id

            print("✅ Demo employee created")

        else:

            print(
                "✅ Demo employee already exists"
            )

        # ---------------------------------------------------------
        # Demo user
        # ---------------------------------------------------------

        user = users.find_one(
            {
                "username": self.DEMO_USERNAME
            }
        )

        if user is None:

            print("📝 Creating demo user account...")

            password_hash = (
                self.mongo_auth.hash_password(
                    self.DEMO_PASSWORD
                )
            )

            users.insert_one(
                {
                    "employee_id": employee["_id"],
                    "username": self.DEMO_USERNAME,
                    "email": self.DEMO_USERNAME,
                    "password_hash": password_hash,
                    "role": "Director",
                    "status": "active",
                    "full_name": self.DEMO_FULL_NAME,
                    "department": "Administration",
                    "require_password_change": False,
                    "created_at": datetime.now(
                        timezone.utc
                    ),
                    "updated_at": datetime.now(
                        timezone.utc
                    ),
                }
            )

            print(
                "✅ Demo user account created"
            )

        else:

            needs_update = False

            if user.get("role") != "Director":

                needs_update = True

            if user.get("status") != "active":

                needs_update = True

            if needs_update:

                users.update_one(
                    {
                        "_id": user["_id"]
                    },
                    {
                        "$set": {
                            "role": "Director",
                            "status": "active",
                            "updated_at": datetime.now(
                                timezone.utc
                            ),
                        }
                    },
                )

                print(
                    "✅ Demo user account updated"
                )

            else:

                print(
                    "✅ Demo user account already exists and is correct"
                )

    # =============================================================
    # ADD EMPLOYEE DIRECTLY TO MONGODB
    # =============================================================

    def add_employee_direct(
        self,
        employee_data,
    ):
        """
        Add an employee directly to MongoDB.

        MongoDB is the source of truth for employee records.
        """

        employees = self.mongodb.get_collection(
            "employees"
        )

        users = self.mongodb.get_collection(
            "users"
        )

        # ---------------------------------------------------------
        # Check duplicate email
        # ---------------------------------------------------------

        email = employee_data.get(
            "email"
        )

        if email:

            existing = employees.find_one(
                {
                    "email": email
                }
            )

            if existing:

                print(
                    f"⚠️ Employee already exists: "
                    f"{existing['_id']}"
                )

                return existing

        # ---------------------------------------------------------
        # Add timestamp
        # ---------------------------------------------------------

        employee_data.setdefault(
            "created_at",
            datetime.now(timezone.utc),
        )

        employee_data.setdefault(
            "clocked_in",
            False,
        )

        # ---------------------------------------------------------
        # Insert employee
        # ---------------------------------------------------------

        result = employees.insert_one(
            employee_data
        )

        employee = employees.find_one(
            {
                "_id": result.inserted_id
            }
        )

        print(
            "✅ Employee added with ID:",
            result.inserted_id,
        )

        # ---------------------------------------------------------
        # Optional user account
        # ---------------------------------------------------------

        username = employee_data.get(
            "username"
        )

        password_hash = employee_data.get(
            "password_hash"
        )

        if username and password_hash:

            existing_user = users.find_one(
                {
                    "username": username
                }
            )

            if existing_user is None:

                users.insert_one(
                    {
                        "employee_id": employee["_id"],
                        "username": username,
                        "email": email,
                        "password_hash": password_hash,
                        "role": employee_data.get(
                            "role",
                            "Staff",
                        ),
                        "status": "active",
                        "full_name": employee_data.get(
                            "full_name",
                            "",
                        ),
                        "department": employee_data.get(
                            "department",
                            "",
                        ),
                        "require_password_change": True,
                        "created_at": datetime.now(
                            timezone.utc
                        ),
                        "updated_at": datetime.now(
                            timezone.utc
                        ),
                        "last_login_at": None,
                    }
                )

                print(
                    "✅ User account created for:",
                    username,
                )

            else:

                print(
                    "ℹ️ User already exists:",
                    username,
                )

        return employee

    # =============================================================
    # RUN
    # =============================================================

    def run(self):

        print(
            "\n🔐 Showing login window..."
        )

        self.controller.show_login()

        login = getattr(
            self.controller,
            "_login_view",
            None,
        )

        if login:

            login.mainloop()

        print(
            "\n👋 Application closed"
        )


# =================================================================
# MAIN
# =================================================================

def main():

    try:

        app = Application()

        app.run()

    except KeyboardInterrupt:

        print(
            "\n👋 Application interrupted"
        )

    except Exception as exc:

        print(
            f"\n❌ Application Error: {exc}"
        )

        import traceback

        traceback.print_exc()


if __name__ == "__main__":

    main()
