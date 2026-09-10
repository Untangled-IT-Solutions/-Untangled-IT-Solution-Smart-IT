# app/views/attendance_view.py
"""Modern Attendance workspace with glass-morphism design and live tracking."""

import customtkinter as ctk
from datetime import datetime
import queue
import threading
import os
from typing import Optional, Dict, Any, List

from app.controllers.attendance_controller import AttendanceController
from app.models.account import UserAccount
from app.services.mongo_attendance_service import MongoAttendanceService
from app.utils.theme import Theme


def _attendance_sync_seconds() -> int:
    try:
        return max(30, int(os.getenv("NEXUS_ATTENDANCE_SYNC_SECONDS", "60")))
    except ValueError:
        return 60


class AttendanceView(ctk.CTkFrame):
    """Modern attendance workspace with glass-morphism UI and live timer."""

    def __init__(
        self,
        master,
        controller: AttendanceController,
        mongo_attendance_service: Optional[MongoAttendanceService] = None,
        current_account: Optional[UserAccount] = None,
        filters: Optional[Dict[str, Any]] = None
    ):
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._mongo = mongo_attendance_service
        self._account = current_account
        self._initial_filters = filters or {}
        self._can_manage = False
        self._employees = []
        self._employees_by_name = {}
        # Backend synchronization and local timer are deliberately separate.
        # The timer must never perform HTTP/network I/O from Tkinter's main thread.
        self._refresh_job = None
        self._timer_job = None
        self._queue_job = None
        self._backend_queue = queue.Queue()
        self._sync_inflight = False
        self._action_inflight = False

        self._calendar_days = 7
        self._is_destroyed = False
        self._last_update_time = 0
        self._backend_refresh_seconds = _attendance_sync_seconds()
        self._retry_count = 0
        self._max_retries = 3

        # Last authoritative state from MongoAttendanceService.
        self._timer_state = None
        self._timer_record = None
        self._weekly_total = 0.0
        self._monthly_total = 0.0
        self._status_colors = {
            "clocked_in": "#4CAF50",
            "on_break": "#FFC107",
            "clocked_out": "#9E9E9E",
            "not_started": "#757575",
            "early": "#FFC107",
            "on_time": "#4CAF50",
            "late": "#E53935",
            "absent": "#757575",
        }
        
        try:
            checker = getattr(controller, "can_manage_attendance", None)
            self._can_manage = bool(checker()) if callable(checker) else False
        except Exception:
            self._can_manage = False
            
        if self._can_manage:
            try:
                self._employees = controller.get_employees() or []
                self._employees_by_name = {
                    e.full_name: e for e in self._employees 
                    if getattr(e, "id", None) is not None
                }
            except Exception:
                self._employees = []
                self._employees_by_name = {}

        self._build_layout()

        # Start a local one-second display tick. It only reads cached state and
        # calculates elapsed time locally; it never calls the backend.
        self._timer_job = self.after(1000, self._local_timer_tick)

        # All backend I/O starts in a worker thread.
        self._queue_job = self.after(50, self._drain_backend_queue)
        self._sync_from_backend()

    def _build_layout(self):
        # Main grid - fixed proportions
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        # === HEADER ===
        header_frame = ctk.CTkFrame(self, fg_color="transparent", height=60)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=30, pady=(20, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_propagate(False)

        # Header left - Title
        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_frame,
            text="⏱ Attendance",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(side="left")

        # Status dot
        self._status_dot = ctk.CTkLabel(
            title_frame,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color="#757575",
        )
        self._status_dot.pack(side="left", padx=(12, 0))

        self._status_dot_label = ctk.CTkLabel(
            title_frame,
            text="Not started",
            font=ctk.CTkFont(size=13),
            text_color=Theme.MUTED_TEXT,
        )
        self._status_dot_label.pack(side="left", padx=(4, 0))

        # Header right - Date/time
        self._datetime_label = ctk.CTkLabel(
            header_frame,
            text=datetime.now().strftime("%A, %d %B %Y • %H:%M"),
            font=ctk.CTkFont(size=13),
            text_color=Theme.MUTED_TEXT,
        )
        self._datetime_label.grid(row=0, column=1, sticky="e")
        self._update_datetime()

        # === MAIN CONTENT ===
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=(0, 20))
        content_frame.grid_columnconfigure(0, weight=1, minsize=400)
        content_frame.grid_columnconfigure(1, weight=1, minsize=400)
        content_frame.grid_rowconfigure(0, weight=1)

        # LEFT PANEL
        self.left_panel = ctk.CTkFrame(
            content_frame,
            fg_color=Theme.PANEL,
            corner_radius=16,
            border_width=1,
            border_color=Theme.BORDER,
        )
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.left_panel.grid_columnconfigure(0, weight=1)

        # RIGHT PANEL
        self.right_panel = ctk.CTkFrame(
            content_frame,
            fg_color=Theme.PANEL,
            corner_radius=16,
            border_width=1,
            border_color=Theme.BORDER,
        )
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(3, weight=1)

        # === LEFT PANEL CONTENT ===
        # Employee selector
        if self._can_manage and self._employees_by_name:
            emp_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
            emp_frame.grid(row=0, column=0, padx=20, pady=(16, 8), sticky="ew")
            emp_frame.grid_columnconfigure(0, weight=0)
            emp_frame.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                emp_frame,
                text="👤 Employee",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=Theme.MUTED_TEXT,
            ).grid(row=0, column=0, padx=(0, 12), sticky="w")

            names = list(self._employees_by_name.keys())
            self.employee_menu = ctk.CTkOptionMenu(
                emp_frame,
                values=names,
                fg_color=Theme.PANEL_ALT,
                button_color=Theme.ACCENT,
                button_hover_color=Theme.ACCENT_HOVER,
                text_color=Theme.TEXT,
                dropdown_text_color=Theme.TEXT,
                dropdown_fg_color=Theme.PANEL,
                dropdown_hover_color=Theme.PANEL_ALT,
                command=lambda _v: self.refresh(),
                font=ctk.CTkFont(size=13),
            )
            self.employee_menu.set(names[0])
            self.employee_menu.grid(row=0, column=1, sticky="ew")
        else:
            self.employee_menu = None
            name = getattr(self._account, "full_name", "Employee")
            emp_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
            emp_frame.grid(row=0, column=0, padx=20, pady=(16, 8), sticky="ew")
            ctk.CTkLabel(
                emp_frame,
                text=f"👤 {name}",
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=Theme.TEXT,
            ).pack(anchor="w")

        # Status card
        status_card = ctk.CTkFrame(
            self.left_panel,
            fg_color=Theme.PANEL_ALT,
            corner_radius=12,
        )
        status_card.grid(row=1, column=0, padx=20, pady=(4, 8), sticky="ew")
        status_card.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            status_card,
            text="Loading…",
            font=ctk.CTkFont(size=14),
            text_color=Theme.TEXT,
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        # Timer - Big and bold
        timer_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        timer_frame.grid(row=2, column=0, padx=20, pady=4, sticky="ew")
        timer_frame.grid_columnconfigure(0, weight=1)

        self.timer_label = ctk.CTkLabel(
            timer_frame,
            text="00:00:00",
            font=ctk.CTkFont(size=44, weight="bold"),
            text_color=Theme.TEXT,
        )
        self.timer_label.grid(row=0, column=0, pady=8)

        # Action buttons
        action_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        action_frame.grid(row=3, column=0, padx=20, pady=(8, 12), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)

        self.clock_in_button = self._modern_button(
            action_frame, "▶ Clock In", self._clock_in, 
            "#4CAF50", "#388E3C", 0, 0
        )
        self.clock_out_button = self._modern_button(
            action_frame, "⏹ Clock Out", self._clock_out,
            Theme.DANGER, Theme.DANGER_HOVER, 0, 1
        )
        self.start_break_button = self._modern_button(
            action_frame, "☕ Break", self._start_break,
            "#FF9800", "#F57C00", 1, 0
        )
        self.end_break_button = self._modern_button(
            action_frame, "✅ End Break", self._end_break,
            "#2196F3", "#1976D2", 1, 1
        )

        # Error label
        self.error_label = ctk.CTkLabel(
            self.left_panel,
            text="",
            text_color=Theme.DANGER,
            font=ctk.CTkFont(size=12),
            wraplength=400,
            justify="left",
        )
        self.error_label.grid(row=4, column=0, padx=20, pady=(4, 8), sticky="w")

        # Totals card
        totals_card = ctk.CTkFrame(
            self.left_panel,
            fg_color=Theme.PANEL_ALT,
            corner_radius=12,
        )
        totals_card.grid(row=5, column=0, padx=20, pady=(4, 16), sticky="ew")
        totals_card.grid_columnconfigure(0, weight=1)
        totals_card.grid_columnconfigure(1, weight=1)
        totals_card.grid_columnconfigure(2, weight=1)

        self.total_label = ctk.CTkLabel(
            totals_card,
            text="📊 Daily: 0.0h\n📈 Weekly: 0.0h\n📅 Monthly: 0.0h",
            font=ctk.CTkFont(size=12),
            text_color=Theme.MUTED_TEXT,
            justify="left",
        )
        self.total_label.grid(row=0, column=0, padx=16, pady=12, sticky="w")

        # === RIGHT PANEL - Attendance Policy + Calendar ===
        policy_card = ctk.CTkFrame(self.right_panel, fg_color=Theme.PANEL_ALT, corner_radius=12)
        policy_card.grid(row=0, column=0, padx=20, pady=(16, 8), sticky="ew")
        policy_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            policy_card, text="📅 Attendance Policy",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=Theme.TEXT
        ).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
        ctk.CTkLabel(
            policy_card, text="08:00–09:00 🟢 On Time  •  After 09:00 🔴 Late",
            font=ctk.CTkFont(size=11), text_color=Theme.MUTED_TEXT
        ).grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        self.calendar_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.calendar_frame.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        self.calendar_frame.grid_columnconfigure(0, weight=1)

        # === RIGHT PANEL - History ===
        history_header = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        history_header.grid(row=2, column=0, padx=20, pady=(16, 8), sticky="ew")
        history_header.grid_columnconfigure(0, weight=1)
        history_header.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            history_header,
            text="📋 Recent Activity",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Theme.TEXT,
        ).grid(row=0, column=0, sticky="w")

        self.week_label = ctk.CTkLabel(
            history_header,
            text="This week",
            font=ctk.CTkFont(size=11),
            text_color=Theme.MUTED_TEXT,
        )
        self.week_label.grid(row=0, column=1, sticky="e")

        # History list
        self.history_frame = ctk.CTkScrollableFrame(
            self.right_panel,
            fg_color="transparent",
            corner_radius=0,
        )
        self.history_frame.grid(row=3, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.history_frame.grid_columnconfigure(0, weight=1)

    def _modern_button(self, parent, text, command, color, hover_color, row, col):
        """Create a modern rounded button."""
        btn = ctk.CTkButton(
            parent,
            text=text,
            height=44,
            corner_radius=12,
            fg_color=color,
            hover_color=hover_color,
            command=command,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        btn.grid(row=row, column=col, padx=6, pady=6, sticky="ew")
        return btn

    def _update_datetime(self):
        """Update the datetime label every second."""
        try:
            if self._is_destroyed:
                return
            now = datetime.now()
            self._datetime_label.configure(
                text=now.strftime("%A, %d %B %Y • %H:%M:%S")
            )
            self.after(1000, self._update_datetime)
        except Exception:
            pass

    def _selected_employee(self):
        if self.employee_menu is not None:
            return self._employees_by_name.get(self.employee_menu.get())
        return None

    def _employee_identity(self):
        employee = self._selected_employee()
        if employee is not None:
            return employee.id, employee.full_name
        return getattr(self._account, "employee_id", None), getattr(self._account, "full_name", "")

    def _run_backend(self, operation, callback, action_name="attendance"):
        """Run network I/O outside Tkinter and marshal the result back safely."""
        if self._is_destroyed:
            return

        def worker():
            try:
                result = operation()
                self._backend_queue.put(("success", result, callback, action_name))
            except Exception as exc:
                self._backend_queue.put(("error", exc, None, action_name))

        threading.Thread(
            target=worker,
            name=f"{action_name}-api",
            daemon=True,
        ).start()

    def _drain_backend_queue(self):
        """Apply background API results on Tkinter's main thread only."""
        if self._is_destroyed:
            return

        try:
            while True:
                kind, payload, callback, action_name = self._backend_queue.get_nowait()
                if kind == "success":
                    if callback:
                        callback(payload)
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

    def _sync_from_backend(self, delay=None):
        """Synchronize authoritative attendance state without blocking the UI."""
        if self._is_destroyed or self._mongo is None:
            return

        if self._sync_inflight:
            return

        employee_id, _ = self._employee_identity()
        if employee_id is None:
            try:
                self.error_label.configure(text="⚠️ No employee linked to this account.")
            except Exception:
                pass
            self._schedule_backend_sync(5000)
            return

        self._sync_inflight = True

        self._run_backend(
            lambda: self._mongo.get_timer_status(employee_id),
            self._accept_backend_state,
            "Attendance sync",
        )

        self._schedule_backend_sync(
            (self._backend_refresh_seconds * 1000) if delay is None else delay
        )

    def _accept_backend_state(self, state):
        if self._is_destroyed:
            return

        self._sync_inflight = False
        self._timer_state = dict(state or {})
        self._timer_record = self._timer_state.get("record")
        self._last_update_time = datetime.now().timestamp()
        self._retry_count = 0

        employee_id, _ = self._employee_identity()
        self._render(
            self._timer_record,
            self._timer_state,
            employee_id,
        )

        # These are supporting data, not timer data, so they update only after
        # an authoritative backend sync instead of every second.
        if employee_id is not None:
            self._update_supporting_data(employee_id)

        try:
            self.error_label.configure(text="")
        except Exception:
            pass

    def _backend_error(self, exc, action_name="attendance"):
        self._sync_inflight = False
        self._action_inflight = False
        self._retry_count += 1
        print(f"⚠️ {action_name} error: {exc}")

        # Keep the last known timer state visible. Retry in the background.
        try:
            self.error_label.configure(text=f"⚠️ {exc}")
        except Exception:
            pass

        if not self._is_destroyed:
            delay = 5000 if self._retry_count >= self._max_retries else 2000
            self._schedule_backend_sync(delay)

    def _schedule_backend_sync(self, delay_ms=None):
        if self._is_destroyed:
            return

        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None

        if delay_ms is None:
            delay_ms = self._backend_refresh_seconds * 1000

        try:
            self._refresh_job = self.after(delay_ms, self._sync_from_backend)
        except Exception:
            self._refresh_job = None

    def refresh(self, force=False):
        """Compatibility entry point: request an asynchronous state refresh."""
        if self._is_destroyed:
            return
        self._sync_from_backend(delay=0 if force else None)

    def _local_timer_tick(self):
        """Update the visible timer every second without touching the backend."""
        if self._is_destroyed:
            return

        self._render_live_timer()

        try:
            self._timer_job = self.after(1000, self._local_timer_tick)
        except Exception:
            self._timer_job = None

    def _render_live_timer(self):
        """Use the same live calculation as MainWindow.TimerWidget."""
        if self._is_destroyed or self._mongo is None:
            return

        record = self._timer_record
        try:
            elapsed = self._mongo.get_live_seconds(record)
            self.timer_label.configure(text=self._format_seconds(elapsed))
        except Exception as exc:
            print(f"⚠️ Timer render error: {exc}")

    def _update_supporting_data(self, employee_id):
        """Refresh calendar/history/totals only after backend synchronization."""
        try:
            self._weekly_total = self._mongo.get_weekly_total(employee_id)
            self._monthly_total = self._mongo.get_monthly_total(employee_id)
        except Exception as exc:
            print(f"⚠️ Error updating totals: {exc}")

        self._render_totals()
        self._render_calendar(employee_id)
        self._render_history(employee_id)

    def _render_totals(self):
        if self._is_destroyed:
            return
        try:
            daily = self._mongo.get_live_hours(self._timer_record) if self._mongo else 0
            self.total_label.configure(
                text=(
                    f"📊 Daily: {daily:.1f}h\n"
                    f"📈 Weekly: {self._weekly_total:.1f}h\n"
                    f"📅 Monthly: {self._monthly_total:.1f}h"
                )
            )
        except Exception as exc:
            print(f"⚠️ Error rendering totals: {exc}")

    def _render(self, record, timer, employee_id):
        """Render cached state only. No network I/O happens here."""
        if self._is_destroyed:
            return

        self._timer_state = timer or {}
        self._timer_record = record

        status = self._timer_state.get("status", "not_started")
        status_display = {
            "not_started": ("Not started", "#757575"),
            "clocked_in": ("Clocked in", "#4CAF50"),
            "on_break": ("On break", "#FFC107"),
            "clocked_out": ("Clocked out", "#9E9E9E"),
        }
        display_text, dot_color = status_display.get(
            status, ("Unknown", "#757575")
        )

        self._status_dot.configure(text_color=dot_color)
        self._status_dot_label.configure(text=display_text)
        self._render_live_timer()

        break_minutes = self._timer_state.get("break_minutes", 0)
        if status == "not_started":
            self.status_label.configure(text="⏳ Not clocked in today")
        elif status == "on_break":
            self.status_label.configure(
                text=f"☕ On break • {break_minutes} min today"
            )
        elif status == "clocked_out":
            try:
                hours = float(record.get("hours_worked", 0) or 0) if record else 0
            except (TypeError, ValueError):
                hours = 0
            self.status_label.configure(
                text=f"✅ Shift completed • {hours:.2f} hours"
            )
        else:
            self.status_label.configure(
                text=f"💼 Clocked in • {break_minutes} min break"
            )

        self._set_actions(
            "disabled" if status in ["clocked_in", "on_break", "clocked_out"] else "normal",
            "disabled" if status in ["not_started", "on_break", "clocked_out"] else "normal",
            "normal" if status == "clocked_in" else "disabled",
            "normal" if status == "on_break" else "disabled",
        )

    @staticmethod
    def _punctuality(record) -> tuple[str, str, str]:
        """Return status, emoji and label for the 08:00-09:00 policy."""
        clock_in = record.get("clock_in_at") if isinstance(record, dict) else getattr(record, "clock_in_at", "")
        if not clock_in:
            return "absent", "⚫", "Absent"
        try:
            from zoneinfo import ZoneInfo
            local = datetime.strptime(clock_in, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=ZoneInfo("UTC")
            ).astimezone(ZoneInfo("Africa/Johannesburg"))
            if local.time() < datetime.strptime("08:00:00", "%H:%M:%S").time():
                return "early", "🟡", "Early"
            if local.time() <= datetime.strptime("09:00:00", "%H:%M:%S").time():
                return "on_time", "🟢", "On Time"
            return "late", "🔴", "Late"
        except (ValueError, TypeError):
            return "unknown", "⚪", "Unknown"

    def _render_calendar(self, employee_id):
        """Render the weekly calendar with error handling."""
        if self._is_destroyed:
            return
            
        for child in self.calendar_frame.winfo_children():
            child.destroy()
        try:
            records = self._mongo.get_weekly_timesheet(employee_id) if self._mongo else []
        except Exception as e:
            print(f"⚠️ Error loading calendar: {e}")
            records = []
            
        by_date = {str(r.get("work_date", "")): r for r in records if isinstance(r, dict)}

        from datetime import date, timedelta
        today = date.today()
        start = today - timedelta(days=6)
        row = ctk.CTkFrame(self.calendar_frame, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew")
        for i in range(7):
            row.grid_columnconfigure(i, weight=1)
            day = start + timedelta(days=i)
            record = by_date.get(day.isoformat())
            status, emoji, _label = self._punctuality(record or {})
            cell = ctk.CTkFrame(
                row, fg_color=Theme.PANEL_ALT, corner_radius=8,
                border_width=1, border_color=self._status_colors.get(status, Theme.BORDER)
            )
            cell.grid(row=0, column=i, padx=2, sticky="nsew")
            ctk.CTkLabel(cell, text=day.strftime("%a"), font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=Theme.MUTED_TEXT).pack(pady=(5, 0))
            ctk.CTkLabel(cell, text=emoji, font=ctk.CTkFont(size=17)).pack()
            ctk.CTkLabel(cell, text=day.strftime("%d"), font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=Theme.TEXT).pack(pady=(0, 5))

    def _render_history(self, employee_id):
        """Render the history with error handling."""
        if self._is_destroyed:
            return
            
        for child in self.history_frame.winfo_children():
            child.destroy()
        
        try:    
            records = self._mongo.get_weekly_timesheet(employee_id) if self._mongo else []
        except Exception as e:
            print(f"⚠️ Error loading history: {e}")
            records = []
            
        if not records:
            empty_frame = ctk.CTkFrame(self.history_frame, fg_color="transparent")
            empty_frame.grid(row=0, column=0, sticky="nsew")
            empty_frame.grid_columnconfigure(0, weight=1)
            empty_frame.grid_rowconfigure(0, weight=1)
            
            ctk.CTkLabel(
                empty_frame,
                text="📭 No records this week",
                font=ctk.CTkFont(size=13),
                text_color=Theme.MUTED_TEXT,
            ).grid(row=0, column=0)
            return

        for row_idx, record in enumerate(records):
            # Each history item as a modern card
            item = ctk.CTkFrame(
                self.history_frame,
                fg_color=Theme.PANEL_ALT,
                corner_radius=8,
            )
            item.grid(row=row_idx, column=0, sticky="ew", pady=(0, 6))
            item.grid_columnconfigure(0, weight=1)
            
            # Get all fields with proper fallbacks
            date = record.get('work_date', '—')
            clock_in = self._time(record.get('clock_in_at'))
            clock_out = self._time(record.get('clock_out_at'))
            break_mins = int(record.get('break_duration_minutes', 0) or 0)
            hours = float(record.get('hours_worked', 0) or 0)
            status_text = record.get('status', '').replace('_', ' ').title() or 'Unknown'
            punctuality, punctuality_emoji, punctuality_label = self._punctuality(record)
            
            # Status color
            status_color = {
                "completed": "#4CAF50",
                "clocked_in": "#2196F3",
                "on_break": "#FFC107",
                "clocked_out": "#9E9E9E",
            }.get(record.get('status', ''), "#9E9E9E")
            
            # Date and status row
            header_row = ctk.CTkFrame(item, fg_color="transparent")
            header_row.grid(row=0, column=0, padx=12, pady=(8, 2), sticky="ew")
            header_row.grid_columnconfigure(0, weight=1)
            
            ctk.CTkLabel(
                header_row,
                text=date,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=Theme.TEXT,
            ).grid(row=0, column=0, sticky="w")
            
            # Status badge
            status_badge = ctk.CTkLabel(
                header_row,
                text=f"{punctuality_emoji} {punctuality_label} • {status_text}",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#1a1a1a",
                fg_color=status_color,
                corner_radius=10,
                padx=10,
                pady=2,
            )
            status_badge.grid(row=0, column=1, sticky="e")
            
            # Details row - show full info
            details_frame = ctk.CTkFrame(item, fg_color="transparent")
            details_frame.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
            details_frame.grid_columnconfigure(0, weight=1)
            details_frame.grid_columnconfigure(1, weight=0)
            details_frame.grid_columnconfigure(2, weight=0)
            
            # Clock in/out times
            ctk.CTkLabel(
                details_frame,
                text=f"🕐 {clock_in} → {clock_out}",
                font=ctk.CTkFont(size=12),
                text_color=Theme.TEXT,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            
            # Break minutes
            ctk.CTkLabel(
                details_frame,
                text=f"☕ {break_mins}min",
                font=ctk.CTkFont(size=12),
                text_color=Theme.MUTED_TEXT,
                anchor="e",
            ).grid(row=0, column=1, padx=(10, 0))
            
            # Hours worked
            ctk.CTkLabel(
                details_frame,
                text=f"⏱ {hours:.1f}h",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=Theme.ACCENT,
                anchor="e",
            ).grid(row=0, column=2, padx=(10, 0))

    def _clock_in(self):
        self._run_action("clock_in")

    def _clock_out(self):
        self._run_action("clock_out")

    def _start_break(self):
        self._run_action("start_break")

    def _end_break(self):
        self._run_action("end_break")

    def _run_action(self, action):
        if self._mongo is None or self._action_inflight or self._is_destroyed:
            return

        employee_id, employee_name = self._employee_identity()
        if employee_id is None:
            self.error_label.configure(
                text="⚠️ No employee linked to this account."
            )
            return

        action_map = {
            "clock_in": (
                lambda: self._mongo.clock_in(employee_id, employee_name),
                "Clock in",
            ),
            "clock_out": (
                lambda: self._mongo.clock_out(employee_id),
                "Clock out",
            ),
            "start_break": (
                lambda: self._mongo.start_break(employee_id),
                "Start break",
            ),
            "end_break": (
                lambda: self._mongo.end_break(employee_id),
                "End break",
            ),
        }

        operation, action_name = action_map.get(action, (None, action))
        if operation is None:
            return

        self._action_inflight = True
        self._set_actions("disabled", "disabled", "disabled", "disabled")

        self._run_backend(
            operation,
            lambda result: self._accept_action_result(result),
            action_name,
        )

    def _accept_action_result(self, result):
        if self._is_destroyed:
            return

        self._action_inflight = False
        self._timer_state = dict(result or {})
        self._timer_record = self._timer_state.get("record")

        employee_id, _ = self._employee_identity()
        self._render(self._timer_record, self._timer_state, employee_id)

        if employee_id is not None:
            self._update_supporting_data(employee_id)

        try:
            self.error_label.configure(text="")
        except Exception:
            pass

    def _set_actions(self, clock_in, clock_out, start_break, end_break):
        try:
            self.clock_in_button.configure(state=clock_in)
            self.clock_out_button.configure(state=clock_out)
            self.start_break_button.configure(state=start_break)
            self.end_break_button.configure(state=end_break)
        except Exception:
            pass

    @staticmethod
    def _format_seconds(seconds):
        seconds = max(0, int(seconds))
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _time(self, value):
        return self._mongo.format_local_time(value) if self._mongo else "—"

    def destroy(self):
        self._is_destroyed = True

        for attr in ("_refresh_job", "_timer_job", "_queue_job"):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
                setattr(self, attr, None)

        try:
            super().destroy()
        except Exception:
            pass
