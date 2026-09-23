# app/controllers/navigation_controller.py
"""Backend API navigation controller with role-based access."""

import customtkinter as ctk
from typing import Optional, Callable, List, Dict, Any

from app.utils.theme import Theme
from app.models.role_permission import can_access_module


class NavigationController:
    """Navigation controller for the Backend API-based desktop client."""

    # Role-based access control
    MANAGER_ROLES = ["Director", "Business Lead", "Operations Manager"]
    STAFF_ROLES = ["Staff", "Intern"]
    
    # Who can see User Management
    USER_MANAGEMENT_ROLES = ["Director", "Operations Manager"]
    
    # Who can see Quote Sync
    QUOTE_SYNC_ROLES = ["Director", "Business Lead", "Operations Manager"]

    def __init__(
        self,
        navigate_callback: Optional[Callable] = None,
        get_current_account: Optional[Callable] = None,
        **services,
    ):
        self._navigate_callback = navigate_callback
        self._get_current_account = get_current_account

        self._notification_service = services.get("notification_service")
        self._people_service = services.get("people_service")
        self._auth_service = services.get("auth_service")
        self._work_service = services.get("work_service")
        self._backend_api = services.get("backend_api")

        self._main_window = None
        self._current_view = "Dashboard"
        self._current_role = "Staff"
        self._current_username = ""
        self._current_full_name = ""
        self._navigation_items_cache = []
        self._navigation_busy = False

        # Get current user info
        self._update_user_info()
        
        print(f"🔐 NavigationController initialized with role: {self._current_role}")

    # ----------------------------------------------------
    # User Info
    # ----------------------------------------------------

    def _update_user_info(self):
        """Update current user information."""
        account = self.get_current_account()
        if account:
            self._current_role = getattr(account, "role", "Staff")
            self._current_username = getattr(account, "username", "")
            self._current_full_name = getattr(account, "full_name", "")
            if not self._current_username:
                self._current_username = getattr(account, "email", "")
        else:
            # Try from auth service
            if self._auth_service:
                session = getattr(self._auth_service, "current_session", None)
                if session:
                    self._current_role = getattr(session, "role", "Staff")
                    self._current_username = getattr(session, "username", "")
                    self._current_full_name = getattr(session, "full_name", "")
                    if not self._current_username:
                        self._current_username = getattr(session, "email", "")
        
        print(f"👤 User info - Role: {self._current_role}, Username: {self._current_username}, Full Name: {self._current_full_name}")

    def is_manager(self) -> bool:
        """Check if current user is a manager."""
        return self._current_role in self.MANAGER_ROLES

    def is_staff(self) -> bool:
        """Check if current user is staff."""
        return self._current_role in self.STAFF_ROLES

    def can_manage_quotes(self) -> bool:
        """Check if current user can manage quotes (full control)."""
        return self._current_role in self.MANAGER_ROLES

    def can_manage_users(self) -> bool:
        """Check if current user can manage users."""
        return self._current_role in self.USER_MANAGEMENT_ROLES

    def can_manage_quote_sync(self) -> bool:
        """Check if current user can manage quote sync."""
        return self._current_role in self.QUOTE_SYNC_ROLES

    # ----------------------------------------------------
    # Callbacks
    # ----------------------------------------------------

    def set_callbacks(self, navigate_callback, get_current_account):
        self._navigate_callback = navigate_callback
        self._get_current_account = get_current_account
        self._update_user_info()
        self._navigation_items_cache = self._build_navigation_items()

    def attach_view(self, main_window):
        self._main_window = main_window

    def set_current_account(self, account):
        """Update the account used by role-aware navigation and rebuild the cache once."""
        self._current_role = getattr(account, "role", "Staff") or "Staff"
        self._current_username = getattr(account, "username", "") or getattr(account, "email", "") or ""
        self._current_full_name = getattr(account, "full_name", "") or ""
        if not self._current_username:
            self._current_username = getattr(account, "email", "") or ""
        self._navigation_items_cache = self._build_navigation_items()

    def navigate(self, destination: str):
        """Navigate to a registered destination without re-querying user state."""
        destination = str(destination or "").strip()
        if not destination:
            return False

        allowed = set(self.get_navigation_items(refresh=False))
        if destination not in allowed:
            print(f"⚠️ Navigation blocked: '{destination}' is not available for role '{self._current_role}'.")
            return False

        if self._navigation_busy:
            print(f"⏳ Navigation already in progress; ignoring duplicate click for '{destination}'.")
            return False

        self._current_view = destination
        if not self._navigate_callback:
            print(f"⚠️ Navigation callback is not configured for '{destination}'.")
            return False

        self._navigation_busy = True
        print(f"➡️ Navigation dispatch: {destination}")
        try:
            result = self._navigate_callback(destination)
            ok = False if result is False else True
            print(f"{'✅' if ok else '❌'} Navigation dispatch result: {destination} -> {ok}")
            return ok
        except Exception as exc:
            print(f"❌ Navigation callback failed for '{destination}': {exc}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._navigation_busy = False

    def get_current_account(self):
        if self._get_current_account:
            return self._get_current_account()
        return None

    # ----------------------------------------------------
    # Quote visibility for Staff
    # ----------------------------------------------------

    def employee_has_quotes(self) -> bool:
        """Check if the current employee has any assigned quotes (Backend API)."""
        if self._backend_api is None:
            return False

        username = (self._current_username or "").strip().lower()
        if not username:
            return False

        try:
            data = self._backend_api.get_quotes()
            quotes = data.get("quotes") or data.get("items") or []
            active = {"assigned", "accepted", "in_progress"}
            for q in quotes:
                status = str(q.get("status") or "").strip().lower()
                if status not in active:
                    continue
                assigned = q.get("assigned_to") or {}
                if isinstance(assigned, dict):
                    fields = [
                        assigned.get("username"),
                        assigned.get("email"),
                        assigned.get("full_name"),
                        assigned.get("display_name"),
                        assigned.get("name"),
                        assigned.get("employee_id"),
                        assigned.get("id"),
                    ]
                else:
                    fields = [assigned]
                if any(str(f or "").strip().lower() == username for f in fields):
                    return True
            return False
        except Exception as e:
            print(f"⚠️ Error checking employee quotes: {e}")
            return False

    # ----------------------------------------------------
    # Get Navigation Items based on role
    # ----------------------------------------------------

    def _build_navigation_items(self) -> List[str]:
        """Build navigation items from the already-known authenticated role."""
        candidates = [
            "Dashboard", "People", "Attendance", "Calendar", "Approvals",
            "Office Requests", "Notifications", "Projects", "Tasks", "Reports",
            "Quote Management", "Order Management", "User Management", "Settings",
        ]
        return [item for item in candidates if can_access_module(self._current_role, item)]

    def get_navigation_items(self, refresh: bool = False) -> List[str]:
        """Return cached navigation items; refresh only after account changes."""
        if refresh or not self._navigation_items_cache:
            self._navigation_items_cache = self._build_navigation_items()
        return list(self._navigation_items_cache)

    # ----------------------------------------------------
    # View Factory
    # ----------------------------------------------------

    def get_view(self, name, workspace, controller):
        """Factory method for creating views with role-based access."""
        
        if name == "Dashboard":
            from app.views.dashboard_view import DashboardView
            return DashboardView(workspace, controller)

        elif name == "Tasks":
            from app.views.task_view import TaskView
            return TaskView(workspace, controller)

        elif name == "Attendance":
            from app.views.attendance_view import AttendanceView
            return AttendanceView(workspace, controller)

        elif name == "Work":
            # Production: Work is task-based (Backend API). Old Mongo quote workspace is retired.
            from app.views.task_view import TaskView
            return TaskView(workspace, controller)

        elif name == "People":
            from app.views.people_view import PeopleView
            return PeopleView(workspace, controller)

        elif name == "Notifications":
            from app.views.notification_view import NotificationView
            return NotificationView(workspace, controller)

        elif name == "Quote Management":
            from app.views.quote_management_view import QuoteManagementView

            return QuoteManagementView(
                master=workspace,
                people_controller=controller,
                notification_controller=self._notification_service,
                auth_service=self._auth_service,
                navigation_controller=self,
                backend_api=self._backend_api,
            )

        elif name == "Order Management":
            from app.views.order_management_view import OrderManagementView

            return OrderManagementView(
                master=workspace,
                people_controller=controller,
                notification_controller=self._notification_service,
                auth_service=self._auth_service,
                navigation_controller=self,
                backend_api=self._backend_api,
            )

        elif name == "User Management":
            if not self.can_manage_users():
                return self._create_access_denied_view(
                    workspace,
                    "User Management",
                    "Only Directors and Operations Managers can access User Management."
                )

            from app.views.user_management_view import UserManagementView
            return UserManagementView(workspace, controller)

        elif name == "Quote Sync":
            if not self.can_manage_quote_sync():
                return self._create_access_denied_view(
                    workspace,
                    "Quote Sync",
                    "Only Directors, Business Leads, and Operations Managers can access Quote Sync."
                )

            return self._create_access_denied_view(
                workspace,
                "Quote Sync",
                "Quote Sync runs on the server. Use Quote Management — all data is loaded from the Backend API.",
            )

        elif name in {"Calendar", "Approvals", "Office Requests", "Projects", "Reports"}:
            from app.views.calendar_view import CalendarView
            from app.views.approval_view import ApprovalView
            from app.views.office_request_view import OfficeRequestView
            from app.views.project_view import ProjectView
            from app.views.report_view import ReportView
            views = {"Calendar": CalendarView, "Approvals": ApprovalView,
                     "Office Requests": OfficeRequestView, "Projects": ProjectView,
                     "Reports": ReportView}
            return views[name](workspace, controller)

        elif name == "Settings":
            from app.views.settings_view import SettingsView
            try:
                return SettingsView(workspace, controller)
            except TypeError:
                return SettingsView(workspace)

        else:
            frame = ctk.CTkFrame(workspace, fg_color="transparent")
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(0, weight=1)
            
            inner = ctk.CTkFrame(frame, fg_color="transparent")
            inner.grid(row=0, column=0)
            
            ctk.CTkLabel(
                inner,
                text=f"{name}",
                font=ctk.CTkFont(size=24, weight="bold"),
                text_color=Theme.TEXT,
            ).pack(pady=(0, 8))
            
            ctk.CTkLabel(
                inner,
                text="Coming Soon",
                font=ctk.CTkFont(size=14),
                text_color=Theme.MUTED_TEXT,
            ).pack()
            
            return frame

    def _create_access_denied_view(self, workspace, title: str, message: str):
        """Create an access denied view."""
        frame = ctk.CTkFrame(workspace, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.grid(row=0, column=0)
        
        ctk.CTkLabel(
            inner,
            text="⛔ Access Denied",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=Theme.DANGER,
        ).pack(pady=(0, 12))
        
        ctk.CTkLabel(
            inner,
            text=f"{title}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(0, 8))
        
        ctk.CTkLabel(
            inner,
            text=message,
            font=ctk.CTkFont(size=13),
            text_color=Theme.MUTED_TEXT,
            justify="center",
            wraplength=500,
        ).pack()
        
        ctk.CTkLabel(
            inner,
            text=f"\nYour role: {self._current_role}",
            font=ctk.CTkFont(size=12),
            text_color=Theme.MUTED_TEXT,
        ).pack()
        
        return frame
