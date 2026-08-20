# app/controllers/navigation_controller.py
"""Navigation controller for managing view switching."""

import customtkinter as ctk
from typing import Optional

from app.controllers.dashboard_controller import DashboardController
from app.controllers.people_controller import PeopleController
from app.controllers.work_controller import WorkController
from app.controllers.attendance_controller import AttendanceController
from app.controllers.calendar_controller import CalendarController
from app.controllers.approval_controller import ApprovalController
from app.controllers.office_request_controller import OfficeRequestController
from app.controllers.notification_controller import NotificationController
from app.controllers.project_controller import ProjectController
from app.controllers.task_controller import TaskController
from app.controllers.report_controller import ReportController
from app.controllers.settings_controller import SettingsController
from app.controllers.quote_sync_controller import QuoteSyncController
from app.controllers.user_management_controller import UserManagementController
from app.services.auth_service import AuthService
from app.services.mongo_auth_service import MongoAuthService
from app.services.mongodb_service import MongoDBService
from app.views.dashboard_view import DashboardView
from app.views.people_view import PeopleView
from app.views.work_view import WorkView
from app.views.attendance_view import AttendanceView
from app.views.calendar_view import CalendarView
from app.views.approval_view import ApprovalView
from app.views.office_request_view import OfficeRequestView
from app.views.notification_view import NotificationView
from app.views.project_view import ProjectView
from app.views.task_view import TaskView
from app.views.report_view import ReportView
from app.views.settings_view import SettingsView
from app.views.quote_sync_view import QuoteSyncView
from app.views.quote_management_view import QuoteManagementView
from app.views.user_management_view import UserManagementView
from app.utils.theme import Theme


class NavigationController:
    """Manages navigation between different views in the main window."""

    NAV_ITEMS = (
        "Dashboard", "Work", "People", "Attendance", "Calendar", "Approvals",
        "Office Requests", "Notifications", "Projects", "Tasks", "Reports",
        "Quote Sync", "Quote Management", "User Management", "Settings",
    )

    def __init__(
        self,
        dashboard_controller: DashboardController,
        people_controller: PeopleController,
        work_controller: WorkController,
        attendance_controller: AttendanceController,
        calendar_controller: CalendarController,
        approval_controller: ApprovalController,
        office_request_controller: OfficeRequestController,
        notification_controller: NotificationController,
        project_controller: ProjectController,
        task_controller: TaskController,
        report_controller: ReportController,
        settings_controller: SettingsController,
        auth_service: AuthService,
        quote_sync_controller: Optional[QuoteSyncController] = None,
        user_management_controller: Optional[UserManagementController] = None,
        mongo_auth_service: Optional[MongoAuthService] = None,
        mongodb_service: Optional[MongoDBService] = None,
    ) -> None:
        """Initialize navigation with all controllers."""
        self._controllers = {
            "Dashboard": dashboard_controller,
            "People": people_controller,
            "Work": work_controller,
            "Attendance": attendance_controller,
            "Calendar": calendar_controller,
            "Approvals": approval_controller,
            "Office Requests": office_request_controller,
            "Notifications": notification_controller,
            "Projects": project_controller,
            "Tasks": task_controller,
            "Reports": report_controller,
            "Settings": settings_controller,
            "Quote Sync": quote_sync_controller,
            "Quote Management": quote_sync_controller,
            "User Management": user_management_controller,
        }
        self._auth_service = auth_service
        self._mongo_auth = mongo_auth_service
        self._mongodb = mongodb_service
        self._work_controller = work_controller
        self._people_controller = people_controller
        self._notification_controller = notification_controller
        self._main_window = None
        self._current_view = "Dashboard"
        self._views_cache = {}

    def attach_view(self, main_window) -> None:
        """Attach the main window reference."""
        self._main_window = main_window
        # Load initial view with a small delay to ensure UI is ready
        self._main_window.after(100, lambda: self.navigate("Dashboard"))

    def navigate(self, destination: str) -> None:
        """Navigate to a specific view."""
        if not self._main_window:
            return

        # Update sidebar active state
        self._main_window.set_active_nav(destination)

        # Get the controller
        controller = self._controllers.get(destination)
        
        # Create or get cached view
        view = self._get_view(destination, controller)
        if view:
            self._main_window.show_workspace_view(view)
            self._current_view = destination
        else:
            # If view creation failed, show dashboard
            print(f"Failed to create view {destination}, showing dashboard")
            self._main_window.show_workspace_view(self._get_view("Dashboard", self._controllers.get("Dashboard")))

    def _get_view(self, name: str, controller) -> Optional:
        """Get or create a view instance."""
        # Check if main window and workspace exist
        if not self._main_window or not self._main_window.workspace:
            return None

        # Check cache - but don't use cached if it's been destroyed
        if name in self._views_cache:
            try:
                if self._views_cache[name].winfo_exists():
                    return self._views_cache[name]
                else:
                    del self._views_cache[name]
            except:
                del self._views_cache[name]

        # Create view based on name with proper parameters
        try:
            view = None
            print(f"Creating view: {name}")
            
            if name == "Dashboard":
                view = DashboardView(self._main_window.workspace, controller)
                
            elif name == "People":
                view = PeopleView(self._main_window.workspace, controller, {})
                
            elif name == "Work":
                view = WorkView(self._main_window.workspace, controller, {})
                
            elif name == "Attendance":
                view = AttendanceView(self._main_window.workspace, controller, {})
                
            elif name == "Calendar":
                view = CalendarView(self._main_window.workspace, controller, {})
                
            elif name == "Approvals":
                view = ApprovalView(self._main_window.workspace, controller, {})
                
            elif name == "Office Requests":
                view = OfficeRequestView(self._main_window.workspace, controller)
                
            elif name == "Notifications":
                view = NotificationView(self._main_window.workspace, controller, {})
                
            elif name == "Projects":
                view = ProjectView(self._main_window.workspace, controller)
                
            elif name == "Tasks":
                view = TaskView(self._main_window.workspace, controller, {})
                
            elif name == "Reports":
                view = ReportView(self._main_window.workspace, controller, {})
                
            elif name == "Settings":
                view = SettingsView(self._main_window.workspace, controller)
                
            elif name == "Quote Sync":
                if controller:
                    view = QuoteSyncView(self._main_window.workspace, controller)
                    print("✅ Quote Sync View created")
                else:
                    print("❌ Quote Sync Controller is None")
                    return self._create_placeholder_view(name, "Quote Sync Controller not available")
                    
            elif name == "Quote Management":
                if self._mongodb and self._work_controller and self._people_controller:
                    view = QuoteManagementView(
                        self._main_window.workspace,
                        self._mongodb,
                        self._work_controller,
                        self._people_controller,
                        self._notification_controller
                    )
                    print("✅ Quote Management View created")
                else:
                    print(f"❌ Quote Management missing dependencies: mongodb={self._mongodb is not None}, work={self._work_controller is not None}, people={self._people_controller is not None}")
                    return self._create_placeholder_view(name, "Quote Management not available - missing dependencies")
                    
            elif name == "User Management":
                if controller:
                    view = UserManagementView(self._main_window.workspace, controller)
                    print("✅ User Management View created")
                else:
                    print("❌ User Management Controller is None")
                    return self._create_placeholder_view(name, "User Management Controller not available")
                    
            else:
                return self._create_placeholder_view(name, f"Unknown view: {name}")

            if view:
                print(f"✅ View {name} created successfully")
                self._views_cache[name] = view
                return view
            else:
                print(f"❌ Failed to create view {name}")
                return self._create_placeholder_view(name, f"Could not create {name} view")

        except Exception as e:
            print(f"❌ Error creating view {name}: {e}")
            import traceback
            traceback.print_exc()
            return self._create_placeholder_view(name, str(e))

    def _create_placeholder_view(self, name: str, message: str = "Module coming soon...") -> ctk.CTkFrame:
        """Create a placeholder view for missing modules."""
        try:
            print(f"Creating placeholder view for: {name} - {message}")
            frame = ctk.CTkFrame(self._main_window.workspace, fg_color=Theme.BG, corner_radius=0)
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(0, weight=1)
            
            content = ctk.CTkFrame(frame, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
            content.grid(row=0, column=0, padx=28, pady=28, sticky="nsew")
            content.grid_columnconfigure(0, weight=1)
            content.grid_rowconfigure(0, weight=1)
            
            ctk.CTkLabel(
                content,
                text=f"📌 {name}\n\n{message}",
                text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_BODY,
                justify="center",
            ).grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
            
            return frame
        except Exception as e:
            print(f"Error creating placeholder view: {e}")
            return None

    def refresh_current_view(self) -> None:
        """Refresh the currently displayed view."""
        if self._current_view:
            if self._current_view in self._views_cache:
                del self._views_cache[self._current_view]
            self.navigate(self._current_view)