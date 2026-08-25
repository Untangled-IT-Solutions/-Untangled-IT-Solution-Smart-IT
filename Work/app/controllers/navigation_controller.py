# app/controllers/navigation_controller.py
"""Navigation controller - MongoDB only with role-based access."""

import customtkinter as ctk
from typing import Optional, Callable, List, Dict, Any

from app.utils.theme import Theme


class NavigationController:
    """Navigation controller for Untangled Workplace - MongoDB only."""

    # Role-based access control
    MANAGER_ROLES = ["Director", "Branch Manager", "Business Lead", "Operations Manager"]
    STAFF_ROLES = ["Staff", "Intern"]
    
    # Who can see User Management
    USER_MANAGEMENT_ROLES = ["Director", "Branch Manager", "Operations Manager"]
    
    # Who can see Quote Sync
    QUOTE_SYNC_ROLES = ["Director", "Branch Manager", "Business Lead", "Operations Manager"]

    def __init__(
        self,
        navigate_callback: Optional[Callable] = None,
        get_current_account: Optional[Callable] = None,
        **services,
    ):
        self._navigate_callback = navigate_callback
        self._get_current_account = get_current_account

        self._database = services.get("database")
        self._mongodb = services.get("mongodb_service")
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

    def attach_view(self, main_window):
        self._main_window = main_window

    def navigate(self, destination: str):
        self._current_view = destination

        if self._navigate_callback:
            self._navigate_callback(destination)

    def get_current_account(self):
        if self._get_current_account:
            return self._get_current_account()
        return None

    # ----------------------------------------------------
    # Quote visibility for Staff
    # ----------------------------------------------------

    def employee_has_quotes(self) -> bool:
        """Check if the current employee has any assigned quotes."""
        if self._mongodb is None:
            return False

        username = self._current_username
        if not username:
            return False

        try:
            collection = self._mongodb.get_collection("quotes")
            
            # Check for quotes assigned to this user
            query = {
                "assigned_to.username": username,
                "status": {"$in": ["assigned", "accepted", "in_progress"]}
            }
            
            count = collection.count_documents(query)
            return count > 0

        except Exception as e:
            print(f"⚠️ Error checking employee quotes: {e}")
            return False

    # ----------------------------------------------------
    # Get Navigation Items based on role
    # ----------------------------------------------------

    def get_navigation_items(self) -> List[str]:
        """
        Get navigation items based on user role.
        
        Quote Management is the single shared workspace for all users.
        """
        # Update user info first
        self._update_user_info()
        
        print(f"🔐 Getting navigation items for role: {self._current_role}")
        
        # Start with base items for all users
        base_items = [
            "Dashboard",
            "People",
            "Attendance",
            "Calendar",
            "Approvals",
            "Office Requests",
            "Notifications",
            "Projects",
            "Tasks",
            "Reports",
        ]
        
        # Quote Management - shown to ALL users
        # This is the single shared workspace
        base_items.append("Quote Management")
        base_items.append("Order Management")
        
        # Directors and Managers get extra management items
        if self.is_manager():
            base_items.append("Quote Sync")
            base_items.append("User Management")
        
        # Add Settings for everyone
        base_items.append("Settings")
        
        print(f"🔐 Navigation items: {base_items}")
        return base_items

    # ----------------------------------------------------
    # View Factory
    # ----------------------------------------------------

    def get_view(self, name, workspace, controller):
        """Factory method for creating views with role-based access."""
        
        if name == "Dashboard":
            from app.views.dashboard_view import DashboardView
            return DashboardView(workspace, controller)

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
                mongodb_service=self._mongodb,
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
                mongodb_service=self._mongodb,
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
                    "Only Directors, Branch Managers, and Operations Managers can access User Management."
                )
            
            from app.views.user_management_view import UserManagementView
            return UserManagementView(workspace, controller)

        elif name == "Quote Sync":
            if not self.can_manage_quote_sync():
                return self._create_access_denied_view(
                    workspace,
                    "Quote Sync",
                    "Only Directors, Branch Managers, Business Leads, and Operations Managers can access Quote Sync."
                )
            
            from app.views.quote_sync_view import QuoteSyncView
            from app.controllers.quote_sync_controller import QuoteSyncController
            
            quote_sync_controller = QuoteSyncController(self._mongodb)
            return QuoteSyncView(workspace, quote_sync_controller)

        elif name == "Settings":
            from app.views.settings_view import SettingsView
            return SettingsView(workspace, controller)

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