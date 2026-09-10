# app/controllers/app_controller.py
"""
Main application coordinator.

Responsible for:
- Login lifecycle
- Main window lifecycle
- Navigation
- View construction
- Logout
- MongoDB service integration
- Quote synchronization
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import customtkinter as ctk

from app.controllers.login_controller import LoginController
from app.controllers.navigation_controller import NavigationController
from app.controllers.search_controller import SearchController
from app.controllers.settings_controller import SettingsController
from app.controllers.user_management_controller import UserManagementController
from app.controllers.notification_controller import NotificationController
from app.controllers.quote_sync_controller import QuoteSyncController
from app.controllers.work_controller import WorkController
from app.controllers.attendance_controller import AttendanceController
from app.controllers.approval_controller import ApprovalController
from app.controllers.office_request_controller import OfficeRequestController
from app.controllers.task_controller import TaskController
from app.controllers.report_controller import ReportController
from app.controllers.calendar_controller import CalendarController
from app.controllers.dashboard_controller import DashboardController
from app.controllers.people_controller import PeopleController
from app.controllers.project_controller import ProjectController

from app.database.database import Database
from app.models.account import UserAccount

from app.services.approval_service import ApprovalService
from app.services.attendance_service import AttendanceService
from app.services.auth_service import AuthService
from app.services.calendar_service import CalendarService
from app.services.dashboard_service import DashboardService
from app.services.mongo_attendance_service import MongoAttendanceService
from app.services.mongo_auth_service import MongoAuthService
from app.services.mongo_notification_service import MongoNotificationService
from app.services.mongodb_service import MongoDBService
from app.services.office_request_service import OfficeRequestService
from app.services.people_service import PeopleService
from app.services.project_service import ProjectService
from app.services.quote_sync_service import QuoteSyncService
from app.services.report_service import ReportService
from app.services.search_service import SearchService
from app.services.work_service import WorkService

from app.utils.theme import Theme

from app.views.login_view import LoginView
from app.views.main_window import MainWindow
from app.views.dashboard_view import DashboardView
from app.views.people_view import PeopleView
from app.views.attendance_view import AttendanceView
from app.views.calendar_view import CalendarView
from app.views.approval_view import ApprovalView
from app.views.office_request_view import OfficeRequestView
from app.views.notification_view import NotificationView
from app.views.project_view import ProjectView
from app.views.report_view import ReportView
from app.views.quote_sync_view import QuoteSyncView
from app.views.quote_management_view import QuoteManagementView
from app.views.order_management_view import OrderManagementView
from app.views.user_management_view import UserManagementView
from app.views.settings_view import SettingsView
from app.views.task_view import TaskView
from app.views.sprint_planning_view import SprintPlanningView


class AppController:
    """Orchestrates login, navigation, view construction and logout."""

    def __init__(
        self,
        auth_service: AuthService,
        dashboard_service: DashboardService,
        people_service: PeopleService,
        work_service: WorkService,
        attendance_service: AttendanceService,
        calendar_service: CalendarService,
        approval_service: ApprovalService,
        office_request_service: OfficeRequestService,
        notification_service: MongoNotificationService,
        search_service: SearchService,
        project_service: ProjectService,
        report_service: ReportService,
        database: Database,
        mongodb_service: Optional[MongoDBService] = None,
        quote_sync_service: Optional[QuoteSyncService] = None,
        mongo_auth_service: Optional[MongoAuthService] = None,
        mongo_attendance_service: Optional[MongoAttendanceService] = None,
        backend_api=None,
    ) -> None:

        # Services
        self._auth_service = auth_service
        self._database = database
        self._mongodb_service = mongodb_service
        self._mongo_auth_service = mongo_auth_service
        self._mongo_attendance_service = mongo_attendance_service
        self._notification_service = notification_service

        self._dashboard_service = dashboard_service
        self._people_service = people_service
        self._work_service = work_service
        self._attendance_service = attendance_service
        self._calendar_service = calendar_service
        self._approval_service = approval_service
        self._office_request_service = office_request_service
        self._search_service = search_service
        self._project_service = project_service
        self._report_service = report_service
        self._quote_sync_service = quote_sync_service
        self._backend_api = backend_api

        # State
        self._login_view: Optional[LoginView] = None
        self._main_window: Optional[MainWindow] = None
        self._current_account: Optional[UserAccount] = None
        self._login_controller: Optional[LoginController] = None

        # Prevent duplicate sync threads
        self._quote_sync_thread: Optional[threading.Thread] = None
        self._quote_sync_running = False

        # Controllers
        self._settings_controller = SettingsController(
            database=self._database,
            auth_service=self._auth_service,
            people_service=self._people_service,
        )

        self._user_management_controller = UserManagementController(
            mongo_auth_service=self._mongo_auth_service,
            people_service=self._people_service,
            auth_service=self._auth_service,
        )

        self._search_controller = SearchController(
            search_service=self._search_service,
        )

        self._dashboard_controller = DashboardController(
            dashboard_service=self._dashboard_service,
        )

        self._people_controller = PeopleController(
            people_service=self._people_service,
        )

        self._work_controller = WorkController(
            work_service=self._work_service,
            people_service=self._people_service,
            notification_service=self._notification_service,
        )

        self._attendance_controller = AttendanceController(
            attendance_service=self._attendance_service,
            people_service=self._people_service,
        )

        self._calendar_controller = CalendarController(
            calendar_service=self._calendar_service,
            people_service=self._people_service,
        )

        self._approval_controller = ApprovalController(
            approval_service=self._approval_service,
            notification_service=self._notification_service,
        )

        self._office_request_controller = OfficeRequestController(
            office_request_service=self._office_request_service,
            people_service=self._people_service,
        )

        self._task_controller = TaskController(
            work_service=self._work_service,
            people_service=self._people_service,
        )

        self._report_controller = ReportController(
            report_service=self._report_service,
        )

        self._project_controller = ProjectController(
            project_service=self._project_service,
        )

        self._navigation_controller = NavigationController(
            auth_service=self._auth_service,
            mongo_auth_service=self._mongo_auth_service,
            mongodb_service=self._mongodb_service,
            database=self._database,
            work_service=self._work_service,
            notification_service=self._notification_service,
        )

        self._navigation_controller.set_callbacks(
            navigate_callback=self._on_navigate,
            get_current_account=self._get_current_account,
        )

        # Flag to track if we're currently logging in
        self._is_logging_in = False

    # ==========================================================
    # LOGIN
    # ==========================================================

    def show_login(self) -> None:
        """Display login window without recreating it."""

        if self._login_view and self._login_view.winfo_exists():
            self._login_view.deiconify()
            self._login_view.lift()
            self._login_view.focus_force()
            return

        self._login_controller = LoginController(
            auth_service=self._auth_service,
            on_success=self._on_login_success,
            mongo_auth_service=self._mongo_auth_service,
        )

        self._login_view = LoginView(self._login_controller)
        self._login_view.protocol(
            "WM_DELETE_WINDOW",
            self._on_login_close,
        )

        print("✅ Login window displayed")

    # ==========================================================
    # LOGIN SUCCESS
    # ==========================================================

    def _on_login_success(self) -> None:
        """Open the main workspace only once."""
        
        # Prevent multiple simultaneous login attempts
        if self._is_logging_in:
            return
        
        self._is_logging_in = True

        try:
            print("🔄 Login successful. Opening application workspace...")

            self._current_account = self._auth_service.current_account

            if self._current_account is None:
                print("❌ No authenticated account found.")
                return

            # Close login
            if self._login_view and self._login_view.winfo_exists():
                self._login_view.destroy()

            self._login_view = None

            # Stop quote sync if running
            self._stop_quote_sync()

            # Recreate services for the new user
            self._recreate_user_services()

            # Create or reuse MainWindow
            if self._main_window and self._main_window.winfo_exists():
                self._main_window.deiconify()
                self._main_window.lift()
                self._main_window.set_current_account(self._current_account)
                self._on_navigate("Dashboard")
            else:
                # Create new main window
                self._main_window = MainWindow(
                    navigation_controller=self._navigation_controller,
                    search_controller=self._search_controller,
                    current_account=self._current_account,
                    on_logout=self._logout,
                )

                self._main_window.set_mongo_services(
                    self._mongo_attendance_service,
                    self._mongo_auth_service,
                )

                print("✅ Main window created successfully")

                # Load dashboard (live People Working / KPIs)
                self._on_navigate("Dashboard")

                # Start sync ONCE
                self._start_quote_sync()

        finally:
            self._is_logging_in = False

    def _recreate_user_services(self) -> None:
        """Recreate user-specific services with fresh state."""
        print("🔄 Recreating user services...")
        
        # Clear any cached data in services
        if hasattr(self._work_service, 'clear_user_data'):
            self._work_service.clear_user_data()
        
        if hasattr(self._attendance_service, 'clear_user_data'):
            self._attendance_service.clear_user_data()
        
        # Update navigation controller with new user
        if hasattr(self._navigation_controller, 'set_current_account'):
            self._navigation_controller.set_current_account(self._current_account)

    # ==========================================================
    # LOGIN CLOSE
    # ==========================================================

    def _on_login_close(self) -> None:
        """Handle login window close."""

        if self._login_view:
            try:
                self._login_view.destroy()
            except Exception:
                pass

        self._login_view = None

    # ==========================================================
    # QUOTE SYNC
    # ==========================================================

    def _start_quote_sync(self) -> None:
        """Start quote sync only once."""

        if self._quote_sync_service is None:
            return

        if self._quote_sync_running:
            return

        self._quote_sync_running = True

        def sync_loop():
            while self._quote_sync_running:
                try:
                    changed = self._quote_sync_service.sync_quotes()

                    # Refresh dashboard only when data changed - schedule on main thread
                    if changed and self._main_window:
                        try:
                            self._main_window.after(
                                0,
                                lambda: self._safe_refresh_dashboard()
                            )
                        except Exception as e:
                            print(f"⚠️ Failed to schedule dashboard refresh: {e}")

                    time.sleep(300)

                except Exception as exc:
                    print(f"⚠️ Quote sync error: {exc}")
                    time.sleep(60)

        self._quote_sync_thread = threading.Thread(
            target=sync_loop,
            daemon=True,
            name="QuoteSyncThread",
        )

        self._quote_sync_thread.start()
        print("✅ Quote synchronization thread started")

    def _stop_quote_sync(self) -> None:
        """Stop the quote sync thread."""
        if self._quote_sync_running:
            self._quote_sync_running = False
            if self._quote_sync_thread:
                try:
                    self._quote_sync_thread.join(timeout=2.0)
                except Exception:
                    pass
            print("🔄 Quote sync stopped")

    def _safe_refresh_dashboard(self) -> None:
        """Safely refresh dashboard from the main thread."""
        try:
            if self._main_window and self._main_window.winfo_exists():
                self._on_navigate("Dashboard")
        except Exception as e:
            print(f"⚠️ Error refreshing dashboard: {e}")

    # ==========================================================
    # NAVIGATION
    # ==========================================================

    def _on_navigate(self, destination: str) -> None:
        """Build and display a workspace view."""

        if self._main_window is None:
            return

        try:
            self._main_window.set_active_nav(destination)
        except Exception:
            pass

        try:
            view = self._create_view(destination)
            if view is not None:
                self._main_window.show_workspace_view(view)
            else:
                error = self._create_error_view(f"View '{destination}' could not be created")
                self._main_window.show_workspace_view(error)

        except Exception as exc:
            print(f"❌ Navigation error: {exc}")
            error = self._create_error_view(str(exc))
            self._main_window.show_workspace_view(error)

    # ==========================================================
    # VIEW FACTORY
    # ==========================================================

    def _create_view(self, destination: str):
        """Factory method for application views."""

        if self._main_window is None:
            raise RuntimeError("Main window is not available.")

        workspace = getattr(self._main_window, "workspace", None)
        if workspace is None:
            raise RuntimeError("MainWindow workspace is not initialized.")

        try:
            if not workspace.winfo_exists():
                raise RuntimeError("MainWindow workspace has been destroyed.")
        except Exception:
            raise RuntimeError("MainWindow workspace is unavailable.")

        if destination == "Dashboard":
            return DashboardView(
                workspace,
                self._dashboard_controller,
            )

        elif destination == "People":
            return PeopleView(
                workspace,
                self._people_controller,
                current_account=self._current_account,
            )

        elif destination == "Attendance":
            return AttendanceView(
                workspace,
                self._attendance_controller,
                mongo_attendance_service=self._mongo_attendance_service,
                current_account=self._current_account,
            )

        elif destination == "Calendar":
            return CalendarView(
                workspace,
                self._calendar_controller,
            )

        elif destination == "Approvals":
            return ApprovalView(
                workspace,
                self._approval_controller,
            )

        elif destination == "Office Requests":
            return OfficeRequestView(
                workspace,
                self._office_request_controller,
                current_account=self._current_account,
            )

        elif destination == "Notifications":
            notification_controller = NotificationController(
                self._notification_service,
                self._mongo_auth_service,
            )

            return NotificationView(
                workspace,
                notification_controller,
            )

        elif destination == "Projects":
            return ProjectView(
                workspace,
                self._project_controller,
                current_account=self._current_account,
            )

        elif destination == "Tasks":
            return TaskView(
                workspace,
                self._task_controller,
                current_account=self._current_account,
            )

        elif destination == "Sprint Planning":
            if not self._navigation_controller.can_access_sprint_planning():
                return self._create_error_view(
                    "Sprint Planning is available only to Ubuntu, Benny and Zandile."
                )
            return SprintPlanningView(
                workspace, self._task_controller, current_account=self._current_account,
            )

        elif destination == "Reports":
            return ReportView(
                workspace,
                self._report_controller,
            )

        elif destination == "Quote Sync":
            if self._quote_sync_service is None:
                return self._create_error_view("Quote Sync Service is not available.")

            quote_controller = QuoteSyncController(
                self._quote_sync_service._mongodb
            )

            return QuoteSyncView(
                workspace,
                quote_controller,
            )

        elif destination == "Quote Management":
            # IMPORTANT: wrap the service in NotificationController so
            # notify_user / notify_executive have a stable interface and
            # accept reference_type / reference_id without TypeError.
            quote_notification_controller = NotificationController(
                self._notification_service,
                self._mongo_auth_service,
            )
            return QuoteManagementView(
                workspace,
                mongodb_service=self._mongodb_service,
                people_controller=self._people_controller,
                notification_controller=quote_notification_controller,
                auth_service=self._auth_service,
                navigation_controller=self._navigation_controller,
                backend_api=self._backend_api,
            )

        elif destination == "Order Management":
            order_notification_controller = NotificationController(
                self._notification_service,
                self._mongo_auth_service,
            )
            return OrderManagementView(
                workspace,
                mongodb_service=self._mongodb_service,
                people_controller=self._people_controller,
                notification_controller=order_notification_controller,
                auth_service=self._auth_service,
                navigation_controller=self._navigation_controller,
                backend_api=self._backend_api,
            )

        elif destination == "User Management":
            return UserManagementView(
                workspace,
                self._user_management_controller,
            )

        elif destination == "Settings":
            return SettingsView(
                workspace,
                self._settings_controller,
            )

        raise ValueError(f"Unknown destination: {destination}")

    # ==========================================================
    # ERROR VIEW
    # ==========================================================

    def _create_error_view(self, message: str):
        """Create a safe error view."""

        if self._main_window is None:
            return None

        workspace = getattr(self._main_window, "workspace", None)
        if workspace is None:
            return None

        frame = ctk.CTkFrame(workspace, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.grid(row=0, column=0)

        ctk.CTkLabel(
            inner,
            text=message,
            font=ctk.CTkFont(size=16),
            text_color=Theme.DANGER,
            wraplength=600,
            justify="center",
        ).pack()

        return frame

    # ==========================================================
    # CURRENT ACCOUNT
    # ==========================================================

    def _get_current_account(self) -> Optional[UserAccount]:
        """Return current authenticated account."""
        return self._current_account

    # ==========================================================
    # LOGOUT
    # ==========================================================

    def _logout(self) -> None:
        """Log out and return to login."""

        print("🔄 Logging out...")

        # Stop quote sync
        self._stop_quote_sync()

        # Clear current account
        self._current_account = None

        # Clear any user-specific state in services
        if hasattr(self._work_service, 'clear_user_data'):
            self._work_service.clear_user_data()
        
        if hasattr(self._attendance_service, 'clear_user_data'):
            self._attendance_service.clear_user_data()

        # Hide main window instead of destroying it
        if self._main_window is not None:
            try:
                if self._main_window.winfo_exists():
                    self._main_window.withdraw()  # Hide the window
                    print("✅ Main window hidden")
            except Exception as exc:
                print(f"⚠️ Main window hide warning: {exc}")

        try:
            self._auth_service.logout()
        except Exception as exc:
            print(f"⚠️ Auth service logout warning: {exc}")

        # Reset login flag
        self._is_logging_in = False

        # Show login screen
        self.show_login()
        print("✅ Returned to login screen")

    # ==========================================================
    # RUN
    # ==========================================================

    def run(self) -> None:
        """Start the application."""

        self.show_login()

        if self._login_view:
            try:
                self._login_view.mainloop()
            except KeyboardInterrupt:
                print("\n👋 Application interrupted by user")
            except Exception as exc:
                print(f"❌ Application event loop error: {exc}")
