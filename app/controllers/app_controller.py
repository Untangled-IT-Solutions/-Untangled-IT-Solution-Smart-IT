# app/controllers/app_controller.py
"""Top-level application flow controller with dual database support and user management."""

from app.controllers.dashboard_controller import DashboardController
from app.controllers.attendance_controller import AttendanceController
from app.controllers.calendar_controller import CalendarController
from app.controllers.approval_controller import ApprovalController
from app.controllers.notification_controller import NotificationController
from app.controllers.office_request_controller import OfficeRequestController
from app.controllers.project_controller import ProjectController
from app.controllers.report_controller import ReportController
from app.controllers.search_controller import SearchController
from app.controllers.settings_controller import SettingsController
from app.controllers.task_controller import TaskController
from app.controllers.login_controller import LoginController
from app.controllers.navigation_controller import NavigationController
from app.controllers.people_controller import PeopleController
from app.controllers.work_controller import WorkController
from app.controllers.quote_sync_controller import QuoteSyncController
from app.controllers.user_management_controller import UserManagementController
from app.database.database import Database
from app.services.auth_service import AuthService
from app.services.dashboard_service import DashboardService
from app.services.attendance_service import AttendanceService
from app.services.calendar_service import CalendarService
from app.services.approval_service import ApprovalService
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
from app.views.login_view import LoginView
from app.views.main_window import MainWindow


class AppController:
    """Coordinates transitions between authentication and the main shell with dual database support."""

    def __init__(
        self,
        # SQLite services
        auth_service: AuthService,
        dashboard_service: DashboardService,
        people_service: PeopleService,
        work_service: WorkService,
        attendance_service: AttendanceService,
        calendar_service: CalendarService,
        approval_service: ApprovalService,
        office_request_service: OfficeRequestService,
        notification_service: NotificationService,
        search_service: SearchService,
        project_service: ProjectService,
        report_service: ReportService,
        database: Database,
        # MongoDB services (optional)
        mongodb_service: MongoDBService = None,
        quote_sync_service: QuoteSyncService = None,
        mongo_auth_service: MongoAuthService = None,
        mongo_attendance_service: MongoAttendanceService = None,
    ) -> None:
        """Initialize all controllers with both SQLite and MongoDB services."""
        
        # Store services
        self._auth_service = auth_service
        self._database = database
        self._mongodb = mongodb_service
        self._mongo_auth = mongo_auth_service
        self._mongo_attendance = mongo_attendance_service
        self._people_service = people_service
        self._work_service = work_service
        self._notification_service = notification_service
        
        # ============================================================
        # Initialize Controllers with SQLite Services
        # ============================================================
        
        # Dashboard Controller
        self._dashboard_controller = DashboardController(
            dashboard_service,
            auth_service,
            attendance_service,
            work_service,
            notification_service,
        )
        
        # People Controller
        self._people_controller = PeopleController(people_service, work_service)
        
        # Work Controller
        self._work_controller = WorkController(work_service, people_service)
        
        # Attendance Controller - Now with MongoDB timer support
        self._attendance_controller = AttendanceController(
            attendance_service,
            people_service,
            auth_service,
            mongo_attendance_service,  # Optional MongoDB timer
        )
        
        # Calendar Controller
        self._calendar_controller = CalendarController(calendar_service, people_service)
        
        # Approval Controller
        self._approval_controller = ApprovalController(approval_service, people_service)
        
        # Office Request Controller
        self._office_request_controller = OfficeRequestController(
            office_request_service, people_service
        )
        
        # Notification Controller
        self._notification_controller = NotificationController(notification_service)
        
        # Search Controller
        self._search_controller = SearchController(search_service)
        
        # Project Controller
        self._project_controller = ProjectController(project_service)
        
        # Task Controller
        self._task_controller = TaskController(work_service, people_service)
        
        # Report Controller
        self._report_controller = ReportController(report_service)
        
        # Settings Controller
        self._settings_controller = SettingsController(
            database, auth_service, people_service
        )
        
        # ============================================================
        # User Management Controller (MongoDB)
        # ============================================================
        self._user_management_controller = None
        if mongo_auth_service and mongodb_service:
            self._user_management_controller = UserManagementController(
                auth_service=mongo_auth_service,
                mongodb=mongodb_service,
            )
            print("✅ User Management Controller initialized")
        
        # ============================================================
        # Quote Sync Controller (MongoDB + SQLite)
        # ============================================================
        self._quote_sync_controller = None
        if quote_sync_service and mongodb_service:
            self._quote_sync_controller = QuoteSyncController(
                quote_sync_service,
                mongodb_service,
                auth_service,
            )
            print("✅ Quote Sync Controller initialized")
        
        # ============================================================
        # UI Windows
        # ============================================================
        self._login_window: LoginView | None = None
        self._main_window: MainWindow | None = None

    def show_login(self) -> None:
        """Display the login view."""
        login_controller = LoginController(
            self._auth_service,
            self._handle_login_success,
            mongo_auth_service=self._mongo_auth,
        )
        try:
            self._login_window = LoginView(login_controller)
            self._login_window.mainloop()
        except Exception as e:
            print(f"Login error: {e}")

    def _handle_login_success(self) -> None:
        """Handle successful login - initialize main window."""
        try:
            if self._login_window is not None:
                self._login_window.destroy()
                self._login_window = None

            # Create navigation controller with all controllers
            navigation_controller = NavigationController(
                self._dashboard_controller,
                self._people_controller,
                self._work_controller,
                self._attendance_controller,
                self._calendar_controller,
                self._approval_controller,
                self._office_request_controller,
                self._notification_controller,
                self._project_controller,
                self._task_controller,
                self._report_controller,
                self._settings_controller,
                self._auth_service,
                quote_sync_controller=self._quote_sync_controller,
                user_management_controller=self._user_management_controller,
                mongo_auth_service=self._mongo_auth,
                mongodb_service=self._mongodb,
            )
            
            # Get current user session
            session = self._auth_service.require_authenticated()
            
            # Create main window - NO user_management_controller parameter!
            self._main_window = MainWindow(
                navigation_controller,
                self._search_controller,
                session.account,
                self._auth_service.logout,
            )
            
            # Store reference to MongoDB services for timer features
            if hasattr(self._main_window, 'set_mongo_services'):
                self._main_window.set_mongo_services(
                    self._mongo_attendance,
                    self._mongo_auth,
                )
            
            navigation_controller.attach_view(self._main_window)
            self._main_window.mainloop()
        except Exception as e:
            print(f"Error handling login success: {e}")
            import traceback
            traceback.print_exc()

    def get_user_management_controller(self):
        """Get the user management controller."""
        return self._user_management_controller

    def get_mongo_auth(self):
        """Get the MongoDB auth service."""
        return self._mongo_auth

    def get_mongo_attendance(self):
        """Get the MongoDB attendance service."""
        return self._mongo_attendance