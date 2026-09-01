# app/views/main_window.py
"""
Main application shell with role-based navigation.

Navigation:
    - Quote Management: Single shared workspace for all users
    - User Management: Only shown for Directors and Operations Managers
    - Quote Sync: Only shown for Directors/Managers
"""

from __future__ import annotations

import customtkinter as ctk
from typing import Optional
import queue

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

from app.controllers.navigation_controller import NavigationController
from app.controllers.search_controller import SearchController
from app.models.account import UserAccount
from app.utils.theme import Theme
from app.utils.async_tasks import start_ui_dispatcher
from app.widgets.sidebar_button import SidebarButton
from app.views.search_view import GlobalSearchModal
from app.services.mongo_attendance_service import MongoAttendanceService
from app.services.mongo_auth_service import MongoAuthService


class TimerWidget(ctk.CTkFrame):
    """Local attendance clock backed by occasional authoritative API syncs."""

    REFRESH_SECONDS = 30

    def __init__(self, master, employee_name: str, employee_id,
                 mongo_attendance: Optional[MongoAttendanceService],
                 mongo_auth: Optional[MongoAuthService] = None):
        super().__init__(master, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        self._mongo_attendance = mongo_attendance
        self._mongo_auth = mongo_auth
        self._employee_name = employee_name
        self._employee_id = employee_id
        self._update_job = None
        self._sync_job = None
        self._is_destroyed = False
        self._state = None
        self._navigation_controller = None  # Timer is intentionally not a navigation owner.
        self._busy = False
        self._backend_queue = queue.Queue()
        self._queue_job = None
        self._build_layout()
        # TimerWidget is a UI component, not the navigation owner.
        # NavigationController must be attached to MainWindow instead.
        self._queue_job = self.after(50, self._drain_backend_queue)
        self.after(100, self._initial_sync)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.status_label = ctk.CTkLabel(self, text="⏱️ Loading...", text_color=Theme.MUTED_TEXT,
                                         font=("Segoe UI", 14, "bold"))
        self.status_label.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        self.timer_display = ctk.CTkLabel(self, text="00:00:00", text_color=Theme.TEXT,
                                          font=("Segoe UI", 24, "bold"))
        self.timer_display.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=0, column=1, rowspan=2, padx=16, pady=8, sticky="e")
        self.clock_button = ctk.CTkButton(button_frame, text="Clock In", width=100, height=36,
                                          fg_color=Theme.SUCCESS, hover_color="#2E7D32",
                                          command=self._toggle_clock)
        self.clock_button.grid(row=0, column=0, pady=(0, 4))
        self.break_button = ctk.CTkButton(button_frame, text="Break", width=100, height=32,
                                          fg_color=Theme.WARNING, hover_color="#F57C00",
                                          command=self._toggle_break, state="disabled")
        self.break_button.grid(row=1, column=0)

    def _initial_sync(self) -> None:
        self._sync_from_backend()
        self._schedule_local_tick()

    def _run_backend(self, operation, on_success=None, action_name="attendance") -> None:
        """Run network I/O off the Tkinter thread and marshal the result back."""
        if self._is_destroyed or self._busy:
            return
        self._busy = True
        self._set_buttons_busy(True)

        import threading

        def worker():
            try:
                result = operation()
                self._backend_queue.put(("success", result, on_success, action_name))
            except Exception as exc:
                self._backend_queue.put(("error", exc, None, action_name))

        threading.Thread(target=worker, name="attendance-api", daemon=True).start()

    def _drain_backend_queue(self) -> None:
        """Apply background HTTP results on Tkinter's main thread only."""
        if self._is_destroyed:
            return

        try:
            while True:
                kind, payload, callback, action_name = self._backend_queue.get_nowait()
                if kind == "success":
                    self._backend_success(payload, callback)
                else:
                    self._backend_error(payload, action_name)
        except queue.Empty:
            pass
        except Exception as exc:
            print(f"⚠️ Attendance UI callback error: {exc}")

        if not self._is_destroyed:
            try:
                self._queue_job = self.after(50, self._drain_backend_queue)
            except Exception:
                self._queue_job = None

    def _backend_success(self, result, callback=None) -> None:
        self._busy = False
        self._set_buttons_busy(False)
        if callback:
            callback(result)
        else:
            self._state = result
            self._render_state()

    def _backend_error(self, exc, action_name="attendance") -> None:
        self._busy = False
        self._set_buttons_busy(False)
        print(f"⚠️ {action_name} error: {exc}")
        # Keep the last known state visible; retry the authoritative sync later.
        self._sync_job = self.after(5000, self._sync_from_backend) if not self._is_destroyed else None

    def _set_buttons_busy(self, busy: bool) -> None:
        if self._is_destroyed:
            return
        try:
            self.clock_button.configure(state="disabled" if busy else "normal")
            if busy:
                self.break_button.configure(state="disabled")
            elif self._state:
                self._render_state()
        except Exception:
            pass

    def _sync_from_backend(self) -> None:
        if self._sync_job is not None:
            try:
                self.after_cancel(self._sync_job)
            except Exception:
                pass
            self._sync_job = None
        if self._is_destroyed or self._mongo_attendance is None or self._employee_id is None:
            return
        self._run_backend(
            lambda: self._mongo_attendance.refresh_state(self._employee_id),
            on_success=self._accept_state,
            action_name="Attendance sync",
        )
        if not self._is_destroyed:
            self._sync_job = self.after(self.REFRESH_SECONDS * 1000, self._sync_from_backend)

    def _accept_state(self, state: dict) -> None:
        self._state = state
        self._render_state()

    def _schedule_local_tick(self) -> None:
        if self._is_destroyed:
            return
        self._render_state()
        self._update_job = self.after(1000, self._schedule_local_tick)

    def _render_state(self) -> None:
        if self._is_destroyed:
            return
        state = self._state or {"state": "not_started", "status": "not_started", "record": None}
        current_state = state.get("state", "not_started")
        current_status = state.get("status", "clocked_out")
        record = state.get("record")

        if current_state == "working" or current_status == "clocked_in":
            label, color = "🟢 Clocked In", Theme.SUCCESS
            elapsed = self._mongo_attendance.get_live_seconds(record) if self._mongo_attendance else 0
            self.clock_button.configure(text="Clock Out", fg_color=Theme.DANGER, hover_color="#C62828", state="normal")
            self.break_button.configure(text="Start Break", fg_color=Theme.WARNING, hover_color="#F57C00", state="normal")
        elif current_state == "on_break" or current_status == "on_break":
            label, color = "☕ On Break", Theme.WARNING
            elapsed = self._mongo_attendance.get_live_seconds(record) if self._mongo_attendance else 0
            self.clock_button.configure(text="Clock Out", fg_color=Theme.DANGER, hover_color="#C62828", state="normal")
            self.break_button.configure(text="End Break", fg_color=Theme.SUCCESS, hover_color="#2E7D32", state="normal")
        elif current_state == "completed" or current_status == "clocked_out":
            label, color = "🔴 Clocked Out", Theme.DANGER
            elapsed = int(float(record.get("hours_worked") or 0) * 3600) if record else 0
            self.clock_button.configure(text="Clock In", fg_color=Theme.SUCCESS, hover_color="#2E7D32", state="disabled")
            self.break_button.configure(text="Break", fg_color=Theme.PANEL_ALT, state="disabled")
        else:
            label, color, elapsed = "🔴 Not Clocked In", Theme.DANGER, 0
            self.clock_button.configure(text="Clock In", fg_color=Theme.SUCCESS, hover_color="#2E7D32", state="normal")
            self.break_button.configure(text="Break", fg_color=Theme.PANEL_ALT, state="disabled")

        self.status_label.configure(text=label, text_color=color)
        self.timer_display.configure(text=self._format_seconds(elapsed))
        if self._busy:
            self.clock_button.configure(state="disabled")
            self.break_button.configure(state="disabled")

    @staticmethod
    def _format_seconds(total_seconds) -> str:
        try:
            total_seconds = max(0, int(float(total_seconds or 0)))
        except (TypeError, ValueError):
            total_seconds = 0
        return f"{total_seconds // 3600:02d}:{(total_seconds % 3600) // 60:02d}:{total_seconds % 60:02d}"

    def _toggle_clock(self) -> None:
        if self._busy or self._is_destroyed or not self._state or self._mongo_attendance is None:
            return
        current_state = self._state.get("state", "not_started")
        current_status = self._state.get("status", "clocked_out")
        if current_state == "not_started" or (current_status == "clocked_out" and not self._state.get("record")):
            op = lambda: self._mongo_attendance.clock_in(self._employee_id, self._employee_name)
            name = "Clock in"
        elif current_state == "completed" or current_status == "clocked_out":
            print("⚠️ Today's attendance has already been completed.")
            return
        elif current_state == "on_break":
            print("⚠️ End the active break before clocking out.")
            return
        else:
            op = lambda: self._mongo_attendance.clock_out(self._employee_id)
            name = "Clock out"
        self._run_backend(op, on_success=self._accept_state, action_name=name)

    def _toggle_break(self) -> None:
        if self._busy or self._is_destroyed or not self._state or self._mongo_attendance is None:
            return
        current_state = self._state.get("state", "not_started")
        current_status = self._state.get("status", "clocked_out")
        if current_state == "working" or current_status == "clocked_in":
            op, name = lambda: self._mongo_attendance.start_break(self._employee_id), "Start break"
        elif current_state == "on_break" or current_status == "on_break":
            op, name = lambda: self._mongo_attendance.end_break(self._employee_id), "End break"
        else:
            print("⚠️ No active attendance session.")
            return
        self._run_backend(op, on_success=self._accept_state, action_name=name)

    def update_employee(self, employee_id, employee_name) -> None:
        self._employee_id = employee_id
        self._employee_name = employee_name
        self._state = None
        self._sync_from_backend()

    def pause(self) -> None:
        for job in (self._update_job, self._sync_job, self._queue_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._update_job = self._sync_job = self._queue_job = None

    def resume(self) -> None:
        if not self._is_destroyed:
            if self._queue_job is None:
                self._queue_job = self.after(50, self._drain_backend_queue)
            self._sync_from_backend()
            self._schedule_local_tick()

    def destroy(self) -> None:
        if self._is_destroyed:
            return
        self._is_destroyed = True
        for job in (self._update_job, self._sync_job, self._queue_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._update_job = self._sync_job = self._queue_job = None
        try:
            super().destroy()
        except Exception:
            pass


class MainWindow(ctk.CTkToplevel):
    """Primary desktop shell with role-based navigation."""

    def __init__(
        self,
        navigation_controller: NavigationController,
        search_controller: SearchController,
        current_account: UserAccount,
        on_logout: object,
        master=None,
    ) -> None:
        super().__init__(master=master)

        self._navigation_controller = navigation_controller
        self._search_controller = search_controller
        self._current_account = current_account
        self._on_logout = on_logout

        self._nav_buttons = {}
        self._active_view = None
        self._timer_widget = None
        self._active_destination = "Dashboard"
        self._logo_image = None
        self._icon_image = None
        self._is_destroyed = False
        self._mongo_attendance = None
        self._mongo_auth = None
        self._nav_items = []
        self._nav_frame = None  # Store reference to nav frame

        self.title(Theme.COMPANY_NAME)
        self.geometry("1400x900")
        self.minsize(1100, 720)
        self.configure(fg_color=Theme.BG)
        self.protocol(
            "WM_DELETE_WINDOW",
            self._handle_window_close,
        )

        # No custom OS/window icon is configured here.
        # This removes the blue square icon from the
        # top-left corner of the Windows title bar.

        self._build_layout()
        # Main-thread poller so background workers can safely deliver results
        # under Python 3.13+/3.14 (cross-thread after() is blocked).
        try:
            start_ui_dispatcher(self)
        except Exception as exc:
            print(f"⚠️ Could not start UI dispatcher: {exc}")
        # Attach navigation before any page is requested.
        try:
            self._navigation_controller.attach_view(self)
        except Exception as exc:
            print(f"⚠️ Could not attach MainWindow to navigation controller: {exc}")

    # ==================================================================
    # SET CURRENT ACCOUNT - SUPPORTS USER SWITCHING
    # ==================================================================

    def set_current_account(self, account: UserAccount) -> None:
        """Update the current user account and refresh UI."""
        if self._is_destroyed:
            return

        print(f"🔄 MainWindow: Updating to new user: {getattr(account, 'full_name', 'Unknown')}")
        
        self._current_account = account
        
        # Update navigation for new user's role
        if hasattr(self._navigation_controller, 'set_current_account'):
            self._navigation_controller.set_current_account(account)
        
        # Rebuild navigation buttons for new role
        self._rebuild_navigation()
        
        # Update timer widget for new employee (don't destroy, just update)
        if self._mongo_attendance and account:
            employee_id = getattr(account, 'employee_id', None)
            employee_name = getattr(account, 'full_name', 'Employee')
            
            if employee_id:
                if self._timer_widget:
                    # Update existing timer widget
                    self._timer_widget.update_employee(employee_id, employee_name)
                    self._timer_widget.resume()
                else:
                    # Create timer if it doesn't exist
                    self.after(100, self._add_timer_to_header)
        
        # After a user switch, always land on Dashboard. Re-navigating to a
        # previous destination (e.g. Quote Management) races with login's
        # own Dashboard open and can leave a half-built workspace.
        self._active_destination = "Dashboard"
        self._navigation_controller.navigate("Dashboard")

    def _rebuild_navigation(self) -> None:
        """Rebuild the navigation buttons for the current user without breaking layout."""
        # Get navigation items based on role
        self._nav_items = (
            self._navigation_controller
            .get_navigation_items()
        )

        print(f"📋 Rebuilding sidebar with items: {self._nav_items}")

        # Find the nav frame
        if self._nav_frame is None or not self._nav_frame.winfo_exists():
            # Try to find it
            for child in self.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, ctk.CTkScrollableFrame):
                            # Check grid position to identify nav frame (row 2 in sidebar)
                            try:
                                grid_info = grandchild.grid_info()
                                if grid_info.get('row') == 2:
                                    self._nav_frame = grandchild
                                    break
                            except:
                                pass
                    if self._nav_frame:
                        break

        if self._nav_frame is None or not self._nav_frame.winfo_exists():
            # If we can't find the nav frame, use the stored reference or rebuild
            print("⚠️ Nav frame not found, attempting to find or create...")
            # Try to find by searching all children
            for child in self.winfo_children():
                if isinstance(child, ctk.CTkFrame):
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, ctk.CTkScrollableFrame):
                            self._nav_frame = grandchild
                            break
                    if self._nav_frame:
                        break
            
            if self._nav_frame is None:
                # Last resort - rebuild layout
                print("⚠️ Nav frame not found, rebuilding layout...")
                self._build_layout()
                return

        # Clear existing buttons (keep the frame)
        for widget in self._nav_frame.winfo_children():
            try:
                widget.destroy()
            except:
                pass
        
        self._nav_buttons.clear()

        # Create new buttons
        for item in self._nav_items:
            button = SidebarButton(
                self._nav_frame,
                text=item,
                command=lambda destination=item: self.navigate_to(destination),
            )

            button.pack(
                fill="x",
                padx=14,
                pady=3,
            )

            self._nav_buttons[item] = button

        # Force update
        self._nav_frame.update_idletasks()

    def clear_user_state(self) -> None:
        """Clear user-specific state on logout."""
        print("🧹 Clearing MainWindow user state...")
        
        # Pause timer updates (don't destroy)
        if self._timer_widget:
            self._timer_widget.pause()
        
        self._current_account = None

    # ==================================================================
    # MONGO SERVICES
    # ==================================================================

    def set_mongo_services(
        self,
        mongo_attendance,
        mongo_auth,
    ):
        if self._is_destroyed:
            return

        self._mongo_attendance = mongo_attendance
        self._mongo_auth = mongo_auth

        if (
            self._mongo_attendance
            and self._current_account
        ):
            try:
                self.after(
                    100,
                    self._add_timer_to_header,
                )
            except Exception:
                pass

    def _add_timer_to_header(self):
        if (
            self._is_destroyed
            or not self._mongo_attendance
            or not self._current_account
        ):
            return

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        # If timer already exists, just update it
        if self._timer_widget is not None:
            try:
                if self._timer_widget.winfo_exists():
                    employee_id = getattr(self._current_account, "employee_id", None)
                    employee_name = getattr(self._current_account, "full_name", "Employee")
                    if employee_id:
                        self._timer_widget.update_employee(employee_id, employee_name)
                        self._timer_widget.resume()
                    return
            except Exception:
                pass
            self._timer_widget = None

        header_widgets = self.grid_slaves(
            row=0,
            column=1,
        )

        if not header_widgets:
            return

        header = header_widgets[0]

        employee_id = getattr(
            self._current_account,
            "employee_id",
            None,
        )

        employee_name = getattr(
            self._current_account,
            "full_name",
            "Employee",
        )

        if employee_id is None:
            print(
                "⚠️ Cannot start header timer: "
                "current account has no employee_id."
            )
            return

        self._timer_widget = TimerWidget(
            header,
            employee_name,
            employee_id,
            self._mongo_attendance,
            self._mongo_auth,
        )

        self._timer_widget.grid(
            row=0,
            column=1,
            padx=(12, 12),
            pady=10,
            sticky="e",
            rowspan=2,
        )

        header.grid_columnconfigure(
            1,
            weight=0,
        )

    # ==================================================================
    # MAIN LAYOUT
    # ==================================================================

    def _build_layout(self):
        if self._is_destroyed:
            return

        self.grid_columnconfigure(
            1,
            weight=1,
        )

        self.grid_rowconfigure(
            1,
            weight=1,
        )

        self._build_sidebar()
        self._build_header()

        self.workspace = ctk.CTkFrame(
            self,
            fg_color=Theme.BG,
            corner_radius=0,
        )

        self.workspace.grid(
            row=1,
            column=1,
            sticky="nsew",
        )

        self.workspace.grid_columnconfigure(
            0,
            weight=1,
        )

        self.workspace.grid_rowconfigure(
            0,
            weight=1,
        )

    def _build_sidebar(self):
        if self._is_destroyed:
            return

        sidebar = ctk.CTkFrame(
            self,
            width=Theme.SIDEBAR_WIDTH,
            fg_color=Theme.PANEL,
            corner_radius=0,
        )

        sidebar.grid(
            row=0,
            column=0,
            rowspan=2,
            sticky="ns",
        )

        sidebar.grid_propagate(False)

        sidebar.grid_columnconfigure(
            0,
            weight=1,
        )

        sidebar.grid_rowconfigure(
            2,
            weight=1,
        )

        # LOGO
        logo_path = Theme.logo_for_current_mode()

        if (
            Image is not None
            and logo_path.exists()
        ):
            try:
                pil_image = Image.open(
                    logo_path
                ).copy()

                self._logo_image = ctk.CTkImage(
                    light_image=pil_image,
                    dark_image=pil_image,
                    size=(188, 150),
                )

                ctk.CTkLabel(
                    sidebar,
                    image=self._logo_image,
                    text="",
                ).grid(
                    row=0,
                    column=0,
                    padx=22,
                    pady=(24, 8),
                    sticky="w",
                )

            except Exception as exc:
                print(
                    f"⚠️ Could not load sidebar logo: {exc}"
                )

                self._create_text_logo(
                    sidebar
                )

        else:
            self._create_text_logo(
                sidebar
            )

        # SUBTITLE
        ctk.CTkLabel(
            sidebar,
            text=Theme.SUBTITLE,
            justify="left",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(
            row=1,
            column=0,
            padx=24,
            pady=(0, 16),
            sticky="w",
        )

        # NAVIGATION
        self._nav_frame = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=Theme.PANEL_ALT,
            scrollbar_button_hover_color=Theme.BORDER,
        )

        self._nav_frame.grid(
            row=2,
            column=0,
            sticky="nsew",
            pady=(0, 16),
        )

        # Get navigation items based on role
        self._nav_items = (
            self._navigation_controller
            .get_navigation_items()
        )

        print(
            f"📋 Building sidebar with items: "
            f"{self._nav_items}"
        )

        for item in self._nav_items:
            button = SidebarButton(
                self._nav_frame,
                text=item,
                command=lambda destination=item: self.navigate_to(destination),
            )

            button.pack(
                fill="x",
                padx=14,
                pady=3,
            )

            self._nav_buttons[item] = button

    def _create_text_logo(
        self,
        sidebar,
    ):
        ctk.CTkLabel(
            sidebar,
            text=Theme.COMPANY_NAME,
            justify="left",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(
            row=0,
            column=0,
            padx=24,
            pady=(30, 8),
            sticky="w",
        )

    def _build_header(self):
        if self._is_destroyed:
            return

        header = ctk.CTkFrame(
            self,
            height=96,
            fg_color=Theme.BG,
            corner_radius=0,
        )

        header.grid(
            row=0,
            column=1,
            sticky="ew",
        )

        header.grid_propagate(False)

        header.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkLabel(
            header,
            text="Operations Workspace",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(
            row=0,
            column=0,
            padx=28,
            pady=(18, 0),
            sticky="w",
        )

        ctk.CTkLabel(
            header,
            text=(
                f"{Theme.COMPANY_LEGAL_NAME} | "
                f"{Theme.SUBTITLE}"
            ),
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(
            row=1,
            column=0,
            padx=28,
            pady=(0, 16),
            sticky="w",
        )

        ctk.CTkButton(
            header,
            text="Logout",
            width=82,
            height=34,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._logout,
        ).grid(
            row=0,
            column=2,
            rowspan=2,
            padx=(0, 28),
            pady=18,
            sticky="e",
        )

    # ==================================================================
    # NAVIGATION
    # ==================================================================

    def set_active_nav(
        self,
        name,
    ):
        if self._is_destroyed:
            return

        self._active_destination = name

        for item, button in self._nav_buttons.items():
            try:
                button.set_active(
                    item == name
                )
            except Exception:
                pass

    def show_workspace_view(
        self,
        view,
        destination: Optional[str] = None,
    ):
        """Display a newly-created view without destroying the current view first.

        This makes navigation transactional: if a destination fails to build,
        the previous working screen remains visible.
        """
        if self._is_destroyed or view is None:
            return False

        try:
            if not view.winfo_exists():
                return False
        except Exception:
            return False

        # Place the new view first. If grid succeeds, the old view can be removed.
        try:
            view.grid(
                row=0,
                column=0,
                sticky="nsew",
                padx=28,
                pady=28,
            )
            view.lift()
            # Force Tk to process the geometry change before replacing the
            # previous workspace. This avoids a blank workspace during
            # rapid navigation between complex CustomTkinter views.
            self.workspace.update_idletasks()
        except Exception as exc:
            print(f"❌ Error displaying view: {exc}")
            try:
                view.destroy()
            except Exception:
                pass
            return False

        old_view = self._active_view
        self._active_view = view
        if destination:
            self._active_destination = destination

        if old_view is not None and old_view is not view:
            try:
                if old_view.winfo_exists():
                    old_view.destroy()
            except Exception:
                pass

        self.set_active_nav(self._active_destination)
        return True

    def navigate_to(self, destination: str) -> None:
        """Navigate safely on Tk's main event loop.

        Sidebar callbacks can originate from nested CustomTkinter widgets.
        Dispatching through ``after(0, ...)`` guarantees the view lifecycle
        runs on Tk's UI thread and prevents a rapid click from racing with
        view destruction/replacement.
        """
        if self._is_destroyed:
            return
        destination = str(destination or "").strip()
        if not destination:
            return

        print(f"🖱️ Navigation click: {destination}")

        def dispatch():
            if self._is_destroyed:
                return
            try:
                result = self._navigation_controller.navigate(destination)
                if result:
                    print(f"🧭 Workspace request completed: {destination}")
                else:
                    print(f"⚠️ Workspace request rejected: {destination}")
            except Exception as exc:
                print(f"❌ Navigation dispatch failed for {destination}: {exc}")
                import traceback
                traceback.print_exc()

        try:
            self.after(0, dispatch)
        except Exception as exc:
            print(f"❌ Could not schedule navigation for {destination}: {exc}")

    def update_navigation(self, navigation_controller: NavigationController) -> None:
        """Update navigation with a new controller."""
        self._navigation_controller = navigation_controller
        self._rebuild_navigation()

    # ==================================================================
    # THEME
    # ==================================================================

    def apply_theme(
        self,
        mode,
    ):
        if self._is_destroyed:
            return

        Theme.apply_mode(
            mode,
            persist=True,
        )

        for widget in self.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

        self.configure(
            fg_color=Theme.BG
        )

        self._nav_buttons.clear()
        self._active_view = None
        self._timer_widget = None
        self._nav_frame = None

        self._build_layout()

        self._navigation_controller.navigate(
            self._active_destination
        )

        if self._mongo_attendance:
            try:
                self.after(
                    100,
                    self._add_timer_to_header,
                )
            except Exception:
                pass

    # ==================================================================
    # LOGOUT
    # ==================================================================

    def _logout(self):
        if self._is_destroyed:
            return

        if callable(self._on_logout):
            try:
                self._on_logout()
            except Exception as exc:
                print(
                    f"⚠️ Logout callback error: {exc}"
                )

    def _handle_window_close(self):
        if self._is_destroyed:
            return

        self._logout()

    def destroy(self):
        if self._is_destroyed:
            return

        self._is_destroyed = True

        if self._timer_widget is not None:
            try:
                self._timer_widget.destroy()
            except Exception:
                pass

            self._timer_widget = None

        self._active_view = None

        try:
            super().destroy()
        except Exception:
            pass