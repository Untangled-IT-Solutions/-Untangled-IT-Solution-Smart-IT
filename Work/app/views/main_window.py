# app/views/main_window.py
"""Main application shell with timer support."""

import customtkinter as ctk
from typing import Optional

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

from app.controllers.navigation_controller import NavigationController
from app.controllers.search_controller import SearchController
from app.models.account import UserAccount
from app.utils.theme import Theme
from app.widgets.sidebar_button import SidebarButton
from app.views.search_view import GlobalSearchModal
from app.services.mongo_attendance_service import MongoAttendanceService
from app.services.mongo_auth_service import MongoAuthService


class TimerWidget(ctk.CTkFrame):
    """Real-time timer widget for attendance tracking."""
    
    def __init__(
        self,
        master,
        employee_name: str,
        mongo_attendance: Optional[MongoAttendanceService],
        mongo_auth: Optional[MongoAuthService],
    ):
        super().__init__(master, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        self._mongo_attendance = mongo_attendance
        self._mongo_auth = mongo_auth
        self._employee_name = employee_name
        self._employee_id = None
        self._update_job = None
        self._is_destroyed = False
        
        self._build_layout()
        self._get_employee_id()
        self._start_timer_updates()
    
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        
        self.status_label = ctk.CTkLabel(
            self,
            text="⏱️ Not Clocked In",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 14, "bold"),
        )
        self.status_label.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        
        self.timer_display = ctk.CTkLabel(
            self,
            text="00:00:00",
            text_color=Theme.TEXT,
            font=("Segoe UI", 24, "bold"),
        )
        self.timer_display.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")
        
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=0, column=1, rowspan=2, padx=16, pady=8, sticky="e")
        button_frame.grid_columnconfigure(0, weight=1)
        
        self.clock_button = ctk.CTkButton(
            button_frame,
            text="Clock In",
            width=100,
            height=36,
            fg_color=Theme.SUCCESS,
            hover_color="#2E7D32",
            command=self._toggle_clock,
        )
        self.clock_button.grid(row=0, column=0, pady=(0, 4))
        
        self.break_button = ctk.CTkButton(
            button_frame,
            text="Break",
            width=100,
            height=32,
            fg_color=Theme.WARNING,
            hover_color="#F57C00",
            command=self._toggle_break,
        )
        self.break_button.grid(row=1, column=0)
        self.break_button.configure(state="disabled")
    
    def _get_employee_id(self) -> None:
        if not self._mongo_attendance or self._is_destroyed:
            return
        try:
            employees_collection = self._mongo_attendance._mongo.get_collection("employees")
            emp = employees_collection.find_one({"full_name": self._employee_name})
            if emp:
                self._employee_id = emp["_id"]
        except Exception:
            pass
    
    def _start_timer_updates(self) -> None:
        self._update_timer()
    
    def _update_timer(self) -> None:
        if self._is_destroyed or not self.winfo_exists():
            return
        if self._mongo_attendance and self._employee_id:
            try:
                status = self._mongo_attendance.get_timer_status(self._employee_id)
                if not self._is_destroyed and self.winfo_exists():
                    self._update_ui_status(status)
            except Exception:
                pass
        if not self._is_destroyed and self.winfo_exists():
            self._update_job = self.after(1000, self._update_timer)
    
    def _update_ui_status(self, status: dict) -> None:
        if self._is_destroyed or not self.winfo_exists():
            return
        current_status = status.get("status", "clocked_out")
        
        if current_status == "clocked_in":
            elapsed = status.get("elapsed_seconds", 0)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            
            self.status_label.configure(text="🟢 Clocked In", text_color=Theme.SUCCESS)
            self.timer_display.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            self.clock_button.configure(text="Clock Out", fg_color=Theme.DANGER, hover_color="#C62828")
            self.break_button.configure(state="normal")
            
        elif current_status == "on_break":
            elapsed = status.get("break_elapsed_minutes", 0)
            self.status_label.configure(text="☕ On Break", text_color=Theme.WARNING)
            self.timer_display.configure(text=f"{elapsed:02d} min")
            self.break_button.configure(text="End Break", fg_color=Theme.SUCCESS, hover_color="#2E7D32")
            
        elif current_status == "clocked_out":
            self.status_label.configure(text="🔴 Clocked Out", text_color=Theme.DANGER)
            self.timer_display.configure(text="00:00:00")
            self.clock_button.configure(text="Clock In", fg_color=Theme.SUCCESS, hover_color="#2E7D32")
            self.break_button.configure(text="Break", fg_color=Theme.PANEL_ALT, state="disabled")
    
    def _toggle_clock(self) -> None:
        if self._is_destroyed or not self._mongo_attendance or not self._employee_id:
            return
        try:
            status = self._mongo_attendance.get_timer_status(self._employee_id)
            current = status.get("status", "clocked_out")
            if current == "clocked_out":
                self._mongo_attendance.clock_in(self._employee_id, self._employee_name)
            else:
                self._mongo_attendance.clock_out(self._employee_id)
            self._update_timer()
        except Exception:
            pass
    
    def _toggle_break(self) -> None:
        if self._is_destroyed or not self._mongo_attendance or not self._employee_id:
            return
        try:
            status = self._mongo_attendance.get_timer_status(self._employee_id)
            current = status.get("status", "clocked_out")
            if current == "clocked_in":
                self._mongo_attendance.start_break(self._employee_id)
            elif current == "on_break":
                self._mongo_attendance.end_break(self._employee_id)
            self._update_timer()
        except Exception:
            pass
    
    def destroy(self) -> None:
        self._is_destroyed = True
        if self._update_job:
            try:
                self.after_cancel(self._update_job)
            except:
                pass
        super().destroy()


class MainWindow(ctk.CTk):
    """Primary desktop shell with sidebar, header, and workspace."""

    NAV_ITEMS = (
        "Dashboard", "Work", "People", "Attendance", "Calendar", "Approvals",
        "Office Requests", "Notifications", "Projects", "Tasks", "Reports", 
        "Quote Sync", "Quote Management", "User Management", "Settings",
    )

    def __init__(
        self,
        navigation_controller: NavigationController,
        search_controller: SearchController,
        current_account: UserAccount,
        on_logout: object,
    ) -> None:
        super().__init__()
        self._navigation_controller = navigation_controller
        self._search_controller = search_controller
        self._current_account = current_account
        self._on_logout = on_logout
        self._nav_buttons = {}
        self._active_view = None
        self._active_destination = "Dashboard"
        self._logo_image = None
        self._is_destroyed = False
        self._mongo_attendance = None
        self._mongo_auth = None

        self.title(Theme.COMPANY_NAME)
        self.geometry("1400x900")
        self.minsize(1100, 720)
        self.configure(fg_color=Theme.BG)
        self._set_window_icon()
        self._build_layout()

    def set_mongo_services(self, mongo_attendance, mongo_auth):
        if self._is_destroyed:
            return
        self._mongo_attendance = mongo_attendance
        self._mongo_auth = mongo_auth
        if self._mongo_attendance and self._current_account:
            self._add_timer_to_header()

    def _add_timer_to_header(self):
        if self._is_destroyed:
            return
        try:
            header_widgets = self.grid_slaves(row=0, column=1)
            if not header_widgets:
                return
            header = header_widgets[0]
            timer = TimerWidget(
                header,
                self._current_account.full_name,
                self._mongo_attendance,
                self._mongo_auth,
            )
            timer.grid(row=0, column=4, padx=(10, 0), pady=(12, 0), sticky="e", rowspan=2)
            header.grid_columnconfigure(4, weight=0)
        except Exception:
            pass

    def _build_layout(self):
        if self._is_destroyed:
            return
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_sidebar()
        self._build_header()
        self.workspace = ctk.CTkFrame(self, fg_color=Theme.BG, corner_radius=0)
        self.workspace.grid(row=1, column=1, sticky="nsew")
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(0, weight=1)

    def _build_sidebar(self):
        if self._is_destroyed:
            return
        sidebar = ctk.CTkFrame(self, width=Theme.SIDEBAR_WIDTH, fg_color=Theme.PANEL, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(2, weight=1)

        logo_path = Theme.logo_for_current_mode()
        if Image is not None and logo_path.exists():
            logo = Image.open(logo_path)
            self._logo_image = ctk.CTkImage(logo, size=(188, 150))
            ctk.CTkLabel(sidebar, image=self._logo_image, text="").grid(
                row=0, column=0, padx=22, pady=(24, 8), sticky="w"
            )
        else:
            ctk.CTkLabel(
                sidebar,
                text=Theme.COMPANY_NAME,
                justify="left",
                text_color=Theme.TEXT,
                font=Theme.FONT_HEADING,
            ).grid(row=0, column=0, padx=24, pady=(30, 8), sticky="w")
        
        ctk.CTkLabel(
            sidebar,
            text=Theme.SUBTITLE,
            justify="left",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=1, column=0, padx=24, pady=(0, 16), sticky="w")

        nav_frame = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=Theme.PANEL_ALT,
            scrollbar_button_hover_color=Theme.BORDER,
        )
        nav_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 16))
        
        for item in self.NAV_ITEMS:
            button = SidebarButton(
                nav_frame,
                text=item,
                command=lambda destination=item: self._navigation_controller.navigate(destination),
            )
            button.pack(fill="x", padx=14, pady=3)
            self._nav_buttons[item] = button

    def _build_header(self):
        if self._is_destroyed:
            return
        header = ctk.CTkFrame(self, height=Theme.HEADER_HEIGHT, fg_color=Theme.BG, corner_radius=0)
        header.grid(row=0, column=1, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Operations Workspace",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, padx=28, pady=(18, 0), sticky="w")

        ctk.CTkLabel(
            header,
            text=f"{Theme.COMPANY_LEGAL_NAME} | {Theme.SUBTITLE}",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=1, column=0, padx=28, pady=(0, 16), sticky="w")

        self.search_entry = ctk.CTkEntry(
            header,
            width=310,
            height=36,
            placeholder_text="Search Nexus",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
            placeholder_text_color=Theme.MUTED_TEXT,
        )
        self.search_entry.grid(row=0, column=1, rowspan=2, padx=28, pady=18, sticky="e")
        self.search_entry.bind("<Return>", self._open_global_search)
        
        ctk.CTkLabel(
            header,
            text=f"{self._current_account.full_name} | {self._current_account.role}",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=0, column=2, padx=(0, 10), pady=18, sticky="e")
        
        ctk.CTkButton(
            header,
            text="Logout",
            width=82,
            height=34,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._logout,
        ).grid(row=0, column=3, padx=(0, 28), pady=18, sticky="e")

    def _open_global_search(self, _event):
        if self._is_destroyed:
            return
        query = self.search_entry.get()
        if query.strip():
            GlobalSearchModal(self, self._search_controller, query)

    def set_active_nav(self, name):
        if self._is_destroyed:
            return
        self._active_destination = name
        for item, button in self._nav_buttons.items():
            button.set_active(item == name)

    def show_workspace_view(self, view):
        if self._is_destroyed:
            return
        if self._active_view is not None:
            try:
                if self._active_view.winfo_exists():
                    self._active_view.destroy()
            except:
                pass
            self._active_view = None
        self._active_view = view
        if view is not None:
            try:
                view.grid(row=0, column=0, sticky="nsew", padx=28, pady=28)
            except Exception as e:
                print(f"Error displaying view: {e}")

    def apply_theme(self, mode):
        if self._is_destroyed:
            return
        Theme.apply_mode(mode, persist=True)
        for widget in self.winfo_children():
            widget.destroy()
        self.configure(fg_color=Theme.BG)
        self._nav_buttons.clear()
        self._build_layout()
        self._navigation_controller.navigate(self._active_destination)
        if self._mongo_attendance:
            self._add_timer_to_header()

    def _logout(self):
        if self._is_destroyed:
            return
        if callable(self._on_logout):
            self._on_logout()
        self.destroy()

    def destroy(self):
        self._is_destroyed = True
        super().destroy()

    def _set_window_icon(self):
        if Image is None or not Theme.ICON_PATH.exists():
            return
        try:
            icon = ctk.CTkImage(Image.open(Theme.ICON_PATH), size=(32, 32))
            self._icon_image = icon
        except OSError:
            pass