# app/application.py
"""Application bootstrap and dependency wiring with dual database support."""

import customtkinter as ctk
import os
import sys
from pathlib import Path

# Add project root to path if needed
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.controllers.app_controller import AppController
from app.database.database import Database
from app.utils.theme import Theme
from app.services.auth_service import AuthService
from app.services.approval_service import ApprovalService
from app.services.attendance_service import AttendanceService
from app.services.calendar_service import CalendarService
from app.services.dashboard_service import DashboardService
from app.services.notification_service import NotificationService
from app.services.office_request_service import OfficeRequestService
from app.services.people_service import PeopleService
from app.services.project_service import ProjectService
from app.services.report_service import ReportService
from app.services.search_service import SearchService
from app.services.work_service import WorkService
from app.services.mongodb_service import MongoDBService
from app.services.quote_sync_service import QuoteSyncService
from app.services.mongo_auth_service import MongoAuthService
from app.services.mongo_attendance_service import MongoAttendanceService


class Application:
    """Composition root for the desktop application with dual database support."""

    def __init__(self) -> None:
        """Initialize both SQLite and MongoDB systems."""
        self._configure_ui()
        
        print("\n" + "="*60)
        print("🚀 UNTANGLED NEXUS - Application Initialization")
        print("="*60)
        
        # ============================================================
        # 1. SQLITE DATABASE (EXISTING - KEPT FOR BACKWARD COMPATIBILITY)
        # ============================================================
        print("\n📁 Initializing SQLite Database...")
        self.database = Database()
        self.database.initialize()
        print("✅ SQLite Database ready")

        # ============================================================
        # 2. MONGODB DATABASE (NEW - FOR TIMER AND ADVANCED FEATURES)
        # ============================================================
        print("\n🔌 Connecting to MongoDB...")
        try:
            self.mongodb = MongoDBService()
            print("✅ MongoDB connected successfully")
        except Exception as e:
            print(f"⚠️ MongoDB connection failed: {e}")
            print("   Continuing with SQLite only mode...")
            self.mongodb = None

        # ============================================================
        # 3. MONGODB SERVICES (NEW FEATURES)
        # ============================================================
        self.mongo_auth = None
        self.mongo_attendance = None
        
        if self.mongodb:
            print("\n🔄 Initializing MongoDB services...")
            try:
                # MongoDB Auth Service - for user management
                self.mongo_auth = MongoAuthService(self.mongodb)
                print("✅ MongoDB Auth Service initialized")
                
                # MongoDB Attendance Service - for real-time timer
                self.mongo_attendance = MongoAttendanceService(self.mongodb)
                print("✅ MongoDB Attendance Service initialized (Timer ready)")
                
                # Sync SQLite employees to MongoDB if needed
                self._sync_employees_to_mongodb()
                
                # Sync SQLite users to MongoDB if needed
                self._sync_users_to_mongodb()
                
            except Exception as e:
                print(f"⚠️ MongoDB service initialization warning: {e}")
                self.mongo_auth = None
                self.mongo_attendance = None
        else:
            self.mongo_auth = None
            self.mongo_attendance = None

        # ============================================================
        # 4. SQLITE SERVICES (YOUR EXISTING SERVICES - KEPT)
        # ============================================================
        print("\n📦 Initializing SQLite services...")
        
        # Authentication Service (SQLite - existing)
        self.auth_service = AuthService(self.database)
        self.auth_service.bootstrap_employee_accounts()
        print("✅ Auth Service ready")
        
        # Notification Service
        self.notification_service = NotificationService(self.database)
        print("✅ Notification Service ready")
        
        # Dashboard Service
        self.dashboard_service = DashboardService(self.database)
        print("✅ Dashboard Service ready")
        
        # People Service
        self.people_service = PeopleService(self.database)
        print("✅ People Service ready")
        
        # Work Service
        self.work_service = WorkService(self.database, self.notification_service)
        print("✅ Work Service ready")
        
        # Attendance Service (SQLite - existing)
        self.attendance_service = AttendanceService(self.database, self.notification_service)
        print("✅ Attendance Service ready")
        
        # Calendar Service
        self.calendar_service = CalendarService(self.database, self.notification_service)
        print("✅ Calendar Service ready")
        
        # Approval Service
        self.approval_service = ApprovalService(self.database, self.notification_service)
        print("✅ Approval Service ready")
        
        # Office Request Service
        self.office_request_service = OfficeRequestService(
            self.database, self.approval_service, self.notification_service
        )
        print("✅ Office Request Service ready")
        
        # Project Service
        self.project_service = ProjectService(self.database)
        print("✅ Project Service ready")
        
        # Report Service
        self.report_service = ReportService(self.database)
        print("✅ Report Service ready")
        
        # Search Service
        self.search_service = SearchService(self.database)
        print("✅ Search Service ready")

        # ============================================================
        # 5. QUOTE SYNC SERVICE (MONGODB + SQLITE)
        # ============================================================
        print("\n📋 Initializing Quote Sync Service...")
        if self.mongodb:
            try:
                self.quote_sync_service = QuoteSyncService(
                    self.database,
                    self.mongodb,
                    self.work_service,
                    self.notification_service
                )
                print("✅ Quote Sync Service ready")
            except Exception as e:
                print(f"⚠️ Quote Sync Service warning: {e}")
                self.quote_sync_service = None
        else:
            self.quote_sync_service = None

        # ============================================================
        # 6. DEMO ACCOUNT SETUP (SQLITE - KEPT)
        # ============================================================
        print("\n👤 Setting up demo account...")
        try:
            demo_account = self.auth_service.ensure_demo_account(
                username="siyandan@untangled.co.za",
                password="Password@untangled123"
            )
            print(f"✅ Demo account ready: {demo_account.username} ({demo_account.role})")
        except Exception as e:
            print(f"⚠️ Demo account setup warning: {e}")
            import traceback
            traceback.print_exc()

        # ============================================================
        # 7. CONTROLLER (WITH DUAL DATABASE SUPPORT)
        # ============================================================
        print("\n🎮 Initializing application controller...")
        self.controller = AppController(
            # SQLite services
            auth_service=self.auth_service,
            dashboard_service=self.dashboard_service,
            people_service=self.people_service,
            work_service=self.work_service,
            attendance_service=self.attendance_service,
            calendar_service=self.calendar_service,
            approval_service=self.approval_service,
            office_request_service=self.office_request_service,
            notification_service=self.notification_service,
            search_service=self.search_service,
            project_service=self.project_service,
            report_service=self.report_service,
            database=self.database,
            
            # MongoDB services (optional)
            mongodb_service=self.mongodb,
            quote_sync_service=self.quote_sync_service,
            mongo_auth_service=self.mongo_auth,
            mongo_attendance_service=self.mongo_attendance,
        )

        print("\n" + "="*60)
        print("✅ APPLICATION INITIALIZATION COMPLETE")
        print("="*60)
        print("\n💡 System Status:")
        print(f"   🗄️  SQLite: {'✅' if self.database else '❌'}")
        print(f"   🍃 MongoDB: {'✅' if self.mongodb else '❌'}")
        print(f"   ⏱️  Timer: {'✅' if self.mongo_attendance else '❌'}")
        print(f"   👤  User Management: {'✅' if self.mongo_auth else '❌'}")
        print("="*60 + "\n")

    def _sync_employees_to_mongodb(self) -> None:
        """Sync SQLite employees to MongoDB for attendance tracking."""
        if not self.mongodb:
            return
            
        print("🔄 Syncing employees to MongoDB...")
        try:
            employees_collection = self.mongodb.get_collection("employees")
        except Exception as e:
            print(f"⚠️ Could not get employees collection: {e}")
            return
        
        # Get employees from SQLite
        try:
            with self.database._get_connection() as conn:
                sqlite_employees = conn.execute(
                    "SELECT * FROM employees"
                ).fetchall()
        except Exception as e:
            print(f"⚠️ Could not fetch employees from SQLite: {e}")
            return
        
        synced_count = 0
        for emp in sqlite_employees:
            # Check if already exists in MongoDB
            try:
                existing = employees_collection.find_one({
                    "$or": [
                        {"employee_number": emp["employee_number"]},
                        {"email": emp["email"]}
                    ]
                })
                
                if not existing:
                    # Convert to MongoDB document
                    mongo_emp = {
                        "employee_number": emp["employee_number"],
                        "first_name": emp["first_name"],
                        "last_name": emp["last_name"],
                        "full_name": emp["full_name"],
                        "position": emp["position"],
                        "department": emp["department"],
                        "role": emp["role"],
                        "reports_to": emp["reports_to"] or "",
                        "mentor": emp["mentor"] or "",
                        "email": emp["email"] or "",
                        "phone": emp["phone"] or "",
                        "status": emp["status"],
                        "employment_type": emp["employment_type"],
                        "date_joined": emp["date_joined"],
                        "current_task": emp["current_task"] or "No active task",
                        "skills": emp["skills"] or "",
                        "permissions": emp["permissions"] or "",
                        "performance_score": float(emp["performance_score"] or 0),
                        "training_progress": float(emp["training_progress"] or 0),
                        "notes": emp["notes"] or "",
                        "clocked_in": False,
                        "sqlite_id": emp["id"],  # Keep reference to SQLite ID
                    }
                    try:
                        employees_collection.insert_one(mongo_emp)
                        synced_count += 1
                    except Exception as e:
                        print(f"   ⚠️ Failed to sync employee {emp['full_name']}: {e}")
            except Exception as e:
                print(f"   ⚠️ Error processing employee {emp.get('full_name', 'unknown')}: {e}")
                continue
        
        if synced_count > 0:
            print(f"   ✅ Synced {synced_count} employees to MongoDB")
        else:
            print("   ✅ All employees already synced or no new employees to sync")

    def _sync_users_to_mongodb(self) -> None:
        """Sync SQLite users to MongoDB for authentication."""
        if not self.mongodb or not self.mongo_auth:
            return
            
        print("🔄 Syncing users to MongoDB...")
        try:
            users_collection = self.mongodb.get_collection("users")
        except Exception as e:
            print(f"⚠️ Could not get users collection: {e}")
            return
        
        # Get users from SQLite
        try:
            with self.database._get_connection() as conn:
                sqlite_users = conn.execute(
                    """
                    SELECT users.*, employees.full_name AS employee_full_name, employees.department
                    FROM users
                    JOIN employees ON employees.id = users.employee_id
                    """
                ).fetchall()
        except Exception as e:
            print(f"⚠️ Could not fetch users from SQLite: {e}")
            return
        
        synced_count = 0
        for user in sqlite_users:
            # Check if already exists in MongoDB
            try:
                existing = users_collection.find_one({
                    "$or": [
                        {"username": user["username"]},
                        {"employee_id": user["employee_id"]}
                    ]
                })
                
                if not existing:
                    # Convert to MongoDB document
                    mongo_user = {
                        "employee_id": user["employee_id"],
                        "username": user["username"],
                        "email": user["email"],
                        "password_hash": user["password_hash"],
                        "role": user["role"],
                        "status": user["status"],
                        "full_name": user["employee_full_name"] or user["full_name"],
                        "department": user["department"],
                        "created_at": user["created_at"],
                        "updated_at": user["updated_at"],
                        "last_login_at": user["last_login_at"],
                    }
                    try:
                        users_collection.insert_one(mongo_user)
                        synced_count += 1
                    except Exception as e:
                        print(f"   ⚠️ Failed to sync user {user['username']}: {e}")
            except Exception as e:
                print(f"   ⚠️ Error processing user {user.get('username', 'unknown')}: {e}")
                continue
        
        if synced_count > 0:
            print(f"   ✅ Synced {synced_count} users to MongoDB")
        else:
            print("   ✅ All users already synced or no new users to sync")

    def run(self) -> None:
        """Open the login window and start the UI event loop."""
        if self.controller:
            self.controller.show_login()
        else:
            print("❌ Application controller not initialized properly.")
            print("   Please check the error messages above.")

    @staticmethod
    def _configure_ui() -> None:
        """Configure CustomTkinter UI settings."""
        # Set appearance mode from saved preference
        Theme.apply_mode()
        
        # Set default window icon if available
        try:
            if Theme.ICON_PATH.exists():
                ctk.set_default_color_theme("dark-blue")
        except Exception:
            pass


def main() -> None:
    """Entry point for the application."""
    try:
        app = Application()
        app.run()
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user")
    except Exception as e:
        print(f"\n❌ Application error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()