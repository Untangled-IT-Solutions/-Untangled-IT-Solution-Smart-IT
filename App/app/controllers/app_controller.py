"""Application controller – production orchestration (Backend API only)."""

from __future__ import annotations

import logging
from typing import Any, Optional

import customtkinter as ctk

from app.services.auth_service import AuthService
from app.services.backend_auth_service import BackendAuthService
from app.services.mongo_attendance_service import MongoAttendanceService
from app.services.people_service import PeopleService
from app.services.dashboard_service import DashboardService
from app.services.attendance_service import AttendanceService
from app.services.work_service import WorkService
from app.services.backend_api_client import BackendAPIClient
from app.services.approval_service import ApprovalService
from app.services.calendar_service import CalendarService
from app.services.office_request_service import OfficeRequestService
from app.services.project_service import ProjectService
from app.services.report_service import ReportService
from app.services.notification_service import NotificationService

from app.controllers.login_controller import LoginController
from app.controllers.task_controller import TaskController
from app.controllers.dashboard_controller import DashboardController
from app.controllers.people_controller import PeopleController
from app.controllers.attendance_controller import AttendanceController
from app.controllers.navigation_controller import NavigationController
from app.controllers.search_controller import SearchController
from app.controllers.user_management_controller import UserManagementController
from app.controllers.approval_controller import ApprovalController
from app.controllers.calendar_controller import CalendarController
from app.controllers.office_request_controller import OfficeRequestController
from app.controllers.project_controller import ProjectController
from app.controllers.report_controller import ReportController
from app.controllers.notification_controller import NotificationController
from app.controllers.settings_controller import SettingsController

from app.views.login_view import LoginView
from app.views.main_window import MainWindow
from app.models.account import UserAccount

logger = logging.getLogger("untangled.app")


class AppController:
    """Orchestrates login → main window lifecycle (Backend API only)."""

    def __init__(
        self,
        auth_service: AuthService,
        mongo_auth_service: BackendAuthService,
        people_service: PeopleService,
        dashboard_service: DashboardService,
        attendance_service: AttendanceService,
        work_service: WorkService,
        backend: BackendAPIClient,
    ) -> None:
        self._auth = auth_service
        self._mongo_auth = mongo_auth_service
        self._people = people_service
        self._dashboard = dashboard_service
        self._attendance = attendance_service
        self._work = work_service
        self._backend = backend
        self._mongo_attendance = MongoAttendanceService(backend)

        # Domain services (all API-backed)
        self._approval_service = ApprovalService(backend, people_service)
        self._calendar_service = CalendarService(backend)
        self._office_request_service = OfficeRequestService(backend, people_service)
        self._project_service = ProjectService(backend)
        self._report_service = ReportService(backend)
        self._notification_service = NotificationService(backend)

        self._login_view: Optional[LoginView] = None
        self._main_window: Optional[MainWindow] = None
        self._hidden_root: Optional[ctk.CTk] = None
        self._current_account: Optional[UserAccount] = None

        # Controllers
        self._notification_controller = NotificationController(
            self._notification_service, mongo_auth_service
        )
        self._task_controller = TaskController(
            work_service,
            people_service,
            notification_service=self._notification_controller,
            get_current_account=lambda: self._current_account,
        )
        self._dashboard_controller = DashboardController(dashboard_service)
        self._people_controller = PeopleController(people_service)
        self._attendance_controller = AttendanceController(
            attendance_service, people_service
        )
        self._user_management_controller = UserManagementController(
            mongo_auth_service=mongo_auth_service,
            people_service=people_service,
            auth_service=auth_service,
        )
        self._approval_controller = ApprovalController(
            self._approval_service, self._notification_service
        )
        self._calendar_controller = CalendarController(
            self._calendar_service, people_service
        )
        self._office_request_controller = OfficeRequestController(
            self._office_request_service, people_service
        )
        self._project_controller = ProjectController(self._project_service)
        self._report_controller = ReportController(self._report_service)
        self._settings_controller = SettingsController(
            auth_service=auth_service,
            people_service=people_service,
            backend=backend,
        )

        self._search_controller = SearchController()
        self._navigation_controller: Optional[NavigationController] = None

    def start(self) -> None:
        self._show_login()

    def _show_login(self) -> None:
        def on_success() -> None:
            self._current_account = self._auth.current_user
            view = self._login_view
            if view is not None:
                try:
                    view.after(80, view.quit)
                except Exception:
                    try:
                        view.quit()
                    except Exception:
                        pass

        login_ctrl = LoginController(
            auth_service=self._auth,
            mongo_auth_service=self._mongo_auth,
            on_success=on_success,
        )
        self._login_view = LoginView(controller=login_ctrl)
        self._login_view.mainloop()

        if self._login_view is not None:
            try:
                self._login_view.destroy()
            except Exception:
                pass
            self._login_view = None

        if self._current_account is not None:
            self._show_main()

    def _show_main(self) -> None:
        account = self._current_account
        if account is None:
            logger.error("No authenticated account")
            self._show_login()
            return

        logger.info("Opening main window for %s (%s)", account.full_name, account.role)

        self._hidden_root = ctk.CTk()
        self._hidden_root.withdraw()

        self._navigation_controller = NavigationController(
            navigate_callback=self._navigate_destination,
            get_current_account=lambda: self._current_account,
            people_service=self._people,
            auth_service=self._auth,
            work_service=self._work,
            backend_api=self._backend,
            notification_service=self._notification_controller,
        )
        self._navigation_controller.set_current_account(account)

        self._main_window = MainWindow(
            navigation_controller=self._navigation_controller,
            search_controller=self._search_controller,
            current_account=account,
            on_logout=self._logout,
            master=self._hidden_root,
        )

        try:
            self._main_window.set_mongo_services(
                self._mongo_attendance,
                self._mongo_auth,
                notification_controller=self._notification_controller,
            )
        except Exception as exc:
            logger.warning("Could not attach attendance services: %s", exc)

        try:
            self._navigation_controller.navigate("Dashboard")
        except Exception as exc:
            logger.warning("Initial Dashboard navigation failed: %s", exc)

        try:
            self._main_window.deiconify()
            self._main_window.lift()
            self._main_window.focus_force()
            self._main_window.update_idletasks()
        except Exception as exc:
            logger.warning("Could not raise main window: %s", exc)

        logger.info("Main window shown – entering mainloop")
        self._hidden_root.mainloop()

    def _navigate_destination(self, destination: str) -> bool:
        """Build and show a workspace view for the NavigationController."""
        window = self._main_window
        if window is None:
            return False

        workspace = getattr(window, "workspace", None)
        if workspace is None:
            return False

        controller_map = {
            "Dashboard": self._dashboard_controller,
            "Tasks": self._task_controller,
            "Work": self._task_controller,
            "People": self._people_controller,
            "Attendance": self._attendance_controller,
            "Approvals": self._approval_controller,
            "Calendar": self._calendar_controller,
            "Office Requests": self._office_request_controller,
            "Projects": self._project_controller,
            "Reports": self._report_controller,
            "Notifications": self._notification_controller,
            "Settings": self._settings_controller,
            "User Management": self._user_management_controller,
        }
        controller = controller_map.get(destination)

        try:
            view = self._navigation_controller.get_view(
                destination, workspace, controller
            )
        except Exception as exc:
            logger.exception("Failed to build view %s", destination)
            print(f"❌ Failed to build view {destination}: {exc}")
            return False

        if view is None:
            return False

        try:
            return bool(window.show_workspace_view(view, destination))
        except Exception as exc:
            logger.exception("Failed to show view %s", destination)
            print(f"❌ Failed to show view {destination}: {exc}")
            return False

    def _logout(self) -> None:
        logger.info("User logged out")
        try:
            self._auth.logout()
        except Exception:
            pass
        self._current_account = None

        if self._main_window is not None:
            try:
                self._main_window.destroy()
            except Exception:
                pass
            self._main_window = None

        if self._hidden_root is not None:
            try:
                self._hidden_root.quit()
                self._hidden_root.destroy()
            except Exception:
                pass
            self._hidden_root = None

        self._show_login()
