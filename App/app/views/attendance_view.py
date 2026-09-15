# app/views/attendance_view.py
"""Modern Attendance workspace matching the Operations Workspace dashboard mockup.

NOTE: The main window already draws the top "Operations Workspace" header and
status/Logout card. This view only renders the Attendance content below that.
"""

import customtkinter as ctk
from datetime import datetime
import queue
import threading
from app.utils.ui_tasks import ui_task, RemoteCall
from typing import Optional, Dict, Any, List

from app.controllers.attendance_controller import AttendanceController
from app.models.account import UserAccount
from app.services.mongo_attendance_service import MongoAttendanceService
from app.utils.theme import Theme


# Design tokens (mockup)
PRIMARY = "#16A34A"
PRIMARY_DARK = "#15803D"
RED = "#DC2626"
RED_HOVER = "#B91C1C"
ORANGE = "#F59E0B"
ORANGE_HOVER = "#D97706"
BLUE = "#2563EB"
BLUE_HOVER = "#1D4ED8"
BG = "#F5F7FA"
CARD = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#0F172A"
MUTED = "#64748B"
SOFT_BANNER = "#F0FDF4"
SOFT_BANNER_BORDER = "#BBF7D0"


class AttendanceView(ctk.CTkFrame):
    """Modern attendance workspace with live timer (content area only)."""

    @ui_task
    def __init__(
        self,
        master,
        controller: AttendanceController,
        mongo_attendance_service: Optional[MongoAttendanceService] = None,
        current_account: Optional[UserAccount] = None,
        filters: Optional[Dict[str, Any]] = None
    ):
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._controller = controller
        self._mongo = mongo_attendance_service
        self._account = current_account
        self._initial_filters = filters or {}

        # Fallback: if navigation did not inject services, pull them from MainWindow
        if self._mongo is None or self._account is None:
            w = master
            for _ in range(8):
                if w is None:
                    break
                if self._mongo is None and getattr(w, "_mongo_attendance", None) is not None:
                    self._mongo = w._mongo_attendance
                if self._account is None and getattr(w, "_current_account", None) is not None:
                    self._account = w._current_account
                w = getattr(w, "master", None)
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
        self._backend_refresh_seconds = 30
        self._retry_count = 0
        self._max_retries = 3

        # Last authoritative state from MongoAttendanceService.
        self._timer_state = None
        self._timer_record = None
        self._weekly_total = 0.0
        self._monthly_total = 0.0
        self._status_colors = {
            "clocked_in": PRIMARY,
            "on_break": ORANGE,
            "clocked_out": "#9E9E9E",
            "not_started": "#757575",
            "early": ORANGE,
            "on_time": PRIMARY,
            "late": RED,
            "absent": "#757575",
        }

        try:
            checker = getattr(controller, "can_manage_attendance", None)
            self._can_manage = bool(checker()) if callable(checker) else False
        except Exception:
            self._can_manage = False

        self._build_layout()

        # Start a local one-second display tick. It only reads cached state and
        # calculates elapsed time locally; it never calls the backend.
        self._timer_job = self.after(1000, self._local_timer_tick)

        # All backend I/O starts in a worker thread.
        self._queue_job = self.after(50, self._drain_backend_queue)

        # Show loader until the first status response arrives (~1–2s on Render).
        self.after(10, lambda: self._show_loading("Loading attendance…"))
        self._sync_from_backend()

    # ------------------------------------------------------------------
    # Layout  (content area only — no duplicate Operations Workspace header)
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Loading overlay (shown while attendance endpoints are in flight)
    # ------------------------------------------------------------------

    def _ensure_loading_overlay(self):
        """Create a semi-transparent overlay with spinner text (once)."""
        if getattr(self, "_loading_overlay", None) is not None:
            return
        # Place over the whole attendance content frame
        self._loading_overlay = ctk.CTkFrame(
            self,
            fg_color=("#F5F7FA", "#F5F7FA"),
            corner_radius=0,
        )
        inner = ctk.CTkFrame(
            self._loading_overlay,
            fg_color=CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER,
            width=280,
            height=120,
        )
        inner.place(relx=0.5, rely=0.4, anchor="center")
        inner.pack_propagate(False)

        self._loading_spinner = ctk.CTkLabel(
            inner,
            text="⏳",
            font=ctk.CTkFont(size=28),
            text_color=PRIMARY,
        )
        self._loading_spinner.pack(pady=(22, 4))

        self._loading_label = ctk.CTkLabel(
            inner,
            text="Loading attendance…",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT,
        )
        self._loading_label.pack(pady=(0, 4))

        ctk.CTkLabel(
            inner,
            text="Waiting for server response",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).pack(pady=(0, 16))

        self._loading_visible = False
        self._spin_job = None
        self._spin_frames = ["⏳", "↻", "⏳", "↺"]
        self._spin_idx = 0

    def _show_loading(self, message: str = "Loading attendance…"):
        if self._is_destroyed:
            return
        try:
            self._ensure_loading_overlay()
            self._loading_label.configure(text=message or "Loading attendance…")
            self._loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._loading_overlay.lift()
            self._loading_visible = True
            self._animate_spinner()
        except Exception as exc:
            print(f"⚠️ show loading failed: {exc}")

    def _hide_loading(self):
        if self._is_destroyed:
            return
        self._loading_visible = False
        if getattr(self, "_spin_job", None) is not None:
            try:
                self.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None
        ov = getattr(self, "_loading_overlay", None)
        if ov is not None:
            try:
                ov.place_forget()
            except Exception:
                pass

    def _animate_spinner(self):
        if self._is_destroyed or not getattr(self, "_loading_visible", False):
            return
        try:
            frames = getattr(self, "_spin_frames", ["⏳", "↻"])
            self._spin_idx = (getattr(self, "_spin_idx", 0) + 1) % len(frames)
            self._loading_spinner.configure(text=frames[self._spin_idx])
            self._spin_job = self.after(400, self._animate_spinner)
        except Exception:
            self._spin_job = None

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # fixed title row
        self.grid_rowconfigure(1, weight=1)  # scrollable body

        self._build_title_row()

        # Vertically scrollable content so nothing is clipped
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self.scroll_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=24,
            pady=(0, 24),
        )
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self._build_content()

    def _build_title_row(self):
        """Attendance title + status + date/time (directly under main app header)."""
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 8))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        # Green circular clock badge
        icon_wrap = ctk.CTkFrame(
            left,
            width=48,
            height=48,
            corner_radius=24,
            fg_color=PRIMARY,
        )
        icon_wrap.pack(side="left")
        icon_wrap.pack_propagate(False)
        ctk.CTkLabel(
            icon_wrap,
            text="⏱",
            font=ctk.CTkFont(size=22),
            text_color="#FFFFFF",
        ).place(relx=0.5, rely=0.5, anchor="center")

        title_block = ctk.CTkFrame(left, fg_color="transparent")
        title_block.pack(side="left", padx=(14, 0))

        ctk.CTkLabel(
            title_block,
            text="Attendance",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w")

        status_line = ctk.CTkFrame(title_block, fg_color="transparent")
        status_line.pack(anchor="w", pady=(2, 0))

        self._status_dot = ctk.CTkLabel(
            status_line,
            text="●",
            font=ctk.CTkFont(size=12),
            text_color="#757575",
        )
        self._status_dot.pack(side="left")

        self._status_dot_label = ctk.CTkLabel(
            status_line,
            text="Not started",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        )
        self._status_dot_label.pack(side="left", padx=(5, 0))

        # Date / time (SAST) — right aligned
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        self._datetime_label = ctk.CTkLabel(
            right,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        )
        self._datetime_label.pack(anchor="e")
        self._update_datetime()

    def _build_content(self):
        # Parent is self.scroll_frame (already padded by the grid call above)
        content = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew", pady=(4, 8))
        content.grid_columnconfigure(0, weight=3, minsize=420)
        content.grid_columnconfigure(1, weight=2, minsize=340)
        content.grid_rowconfigure(0, weight=0)

        # ================================================================
        # LEFT: Today's Attendance
        # ================================================================
        self.left_panel = ctk.CTkFrame(
            content,
            fg_color=CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER,
        )
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        self.left_panel.grid_columnconfigure(0, weight=1)

        # Card title
        ctk.CTkLabel(
            self.left_panel,
            text="📅  Today's Attendance",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 12))

        # Attendance actions always belong to the signed-in employee.
        self.employee_menu = None

        # Status banner
        self._banner = ctk.CTkFrame(
            self.left_panel,
            fg_color=SOFT_BANNER,
            corner_radius=12,
            border_width=1,
            border_color=SOFT_BANNER_BORDER,
        )
        self._banner.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        self._banner.grid_columnconfigure(0, weight=1)
        self._banner.grid_columnconfigure(1, weight=0)

        self.status_label = ctk.CTkLabel(
            self._banner,
            text="⏳  Not clocked in today",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT,
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=16, pady=14)

        self._since_label = ctk.CTkLabel(
            self._banner,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        )
        self._since_label.grid(row=0, column=1, sticky="e", padx=16, pady=14)

        # Large centered live timer
        timer_wrap = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        timer_wrap.grid(row=3, column=0, sticky="ew", padx=20, pady=(12, 4))
        timer_wrap.grid_columnconfigure(0, weight=1)

        self.timer_label = ctk.CTkLabel(
            timer_wrap,
            text="00:00:00",
            font=ctk.CTkFont(size=56, weight="bold"),
            text_color=TEXT,
        )
        self.timer_label.grid(row=0, column=0)

        ctk.CTkLabel(
            timer_wrap,
            text="Current Time",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        ).grid(row=1, column=0, pady=(2, 8))

        # 2×2 equal action buttons
        action_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        action_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=(4, 8))
        action_frame.grid_columnconfigure(0, weight=1, uniform="btn")
        action_frame.grid_columnconfigure(1, weight=1, uniform="btn")

        self.clock_in_button = self._modern_button(
            action_frame, "▶  Clock In", self._clock_in,
            PRIMARY, PRIMARY_DARK, 0, 0
        )
        self.clock_out_button = self._modern_button(
            action_frame, "⏹  Clock Out", self._clock_out,
            RED, RED_HOVER, 0, 1
        )
        self.start_break_button = self._modern_button(
            action_frame, "☕  Start Break", self._start_break,
            ORANGE, ORANGE_HOVER, 1, 0
        )
        self.end_break_button = self._modern_button(
            action_frame, "✅  End Break", self._end_break,
            BLUE, BLUE_HOVER, 1, 1
        )

        # Error label
        self.error_label = ctk.CTkLabel(
            self.left_panel,
            text="",
            text_color=RED,
            font=ctk.CTkFont(size=12),
            wraplength=420,
            justify="left",
        )
        self.error_label.grid(row=5, column=0, sticky="w", padx=20, pady=(0, 4))

        # Today's Summary
        summary = ctk.CTkFrame(
            self.left_panel,
            fg_color="#F8FAFC",
            corner_radius=12,
            border_width=1,
            border_color=BORDER,
        )
        summary.grid(row=6, column=0, sticky="ew", padx=20, pady=(10, 20))
        summary.grid_columnconfigure(0, weight=1)
        summary.grid_columnconfigure(1, weight=1)
        summary.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            summary,
            text="⏱  Today's Summary",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(14, 8))

        self._summary_time_in = self._summary_cell(summary, "Time In", "—", 1, 0)
        self._summary_time_out = self._summary_cell(summary, "Time Out", "—", 1, 1)
        self._summary_break = self._summary_cell(summary, "Break Time", "—", 1, 2)

        # Hidden totals label (kept for API compatibility with _render_totals)
        self.total_label = ctk.CTkLabel(
            self.left_panel,
            text="",
            font=ctk.CTkFont(size=1),
            text_color=BG,
        )

        # ================================================================
        # RIGHT: Policy + Recent Activity
        # ================================================================
        self.right_panel = ctk.CTkFrame(content, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(0, weight=0)
        self.right_panel.grid_rowconfigure(1, weight=1)

        # --- Attendance Policy ---
        policy = ctk.CTkFrame(
            self.right_panel,
            fg_color=CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER,
        )
        policy.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        policy.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            policy,
            text="👥  Team Attendance Today" if self._can_manage else "☰  Attendance Policy",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 12))

        if self._can_manage:
            self.team_summary_label = ctk.CTkLabel(
                policy, text="Loading team attendance…", text_color=MUTED,
                font=ctk.CTkFont(size=12), anchor="w",
            )
            self.team_summary_label.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))
            self.team_frame = ctk.CTkScrollableFrame(
                policy, fg_color="transparent", height=150, corner_radius=0,
            )
            self.team_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 14))
            self.team_frame.grid_columnconfigure(0, weight=1)
        else:
            self.team_summary_label = None
            self.team_frame = None
            self._policy_row(policy, 1, "🕐", "Working Hours", "09:00 AM – 04:00 PM")
            self._policy_separator(policy, 2)
            self._policy_row(policy, 3, "☕", "Break Time", "12:00 PM – 01:00 PM (1 hour)")
            self._policy_separator(policy, 4)
            self._policy_row(policy, 5, "📅", "Late Arrival", "After 09:00 AM (may affect your day's record)")
            self._policy_separator(policy, 6)
            self._policy_row(policy, 7, "🛡", "Early Departure", "Before 04:00 PM (may affect your day's record)", last=True)

        # --- Recent Activity ---
        activity = ctk.CTkFrame(
            self.right_panel,
            fg_color=CARD,
            corner_radius=16,
            border_width=1,
            border_color=BORDER,
        )
        activity.grid(row=1, column=0, sticky="nsew")
        activity.grid_columnconfigure(0, weight=1)
        activity.grid_rowconfigure(1, weight=1)

        act_hdr = ctk.CTkFrame(activity, fg_color="transparent")
        act_hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        act_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            act_hdr,
            text="📈  Recent Activity",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w")

        self.week_label = ctk.CTkLabel(
            act_hdr,
            text="This week",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        )
        self.week_label.grid(row=0, column=1, sticky="e")

        self.history_frame = ctk.CTkScrollableFrame(
            activity,
            fg_color="transparent",
            corner_radius=0,
        )
        self.history_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 16))
        self.history_frame.grid_columnconfigure(0, weight=1)

        # Calendar frame kept for API compatibility (not shown in mockup)
        self.calendar_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent", height=1)

    # ------------------------------------------------------------------
    # Small UI helpers
    # ------------------------------------------------------------------

    def _modern_button(self, parent, text, command, color, hover_color, row, col):
        btn = ctk.CTkButton(
            parent,
            text=text,
            height=48,
            corner_radius=12,
            fg_color=color,
            hover_color=hover_color,
            command=command,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#FFFFFF",
        )
        btn.grid(row=row, column=col, padx=6, pady=6, sticky="ew")
        return btn

    def _summary_cell(self, parent, title, value, row, col):
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=row, column=col, sticky="nsew", padx=10, pady=(0, 16))
        ctk.CTkLabel(
            cell,
            text=title,
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
        ).pack(anchor="w")
        lbl = ctk.CTkLabel(
            cell,
            text=value,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT,
        )
        lbl.pack(anchor="w", pady=(2, 0))
        return lbl

    def _policy_row(self, parent, row, icon, title, subtitle, last=False):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        bottom = 18 if last else 8
        frame.grid(row=row, column=0, sticky="ew", padx=20, pady=(6, bottom))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame,
            text=icon,
            font=ctk.CTkFont(size=16),
            width=28,
        ).grid(row=0, column=0, rowspan=2, sticky="n", pady=(2, 0))

        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        ctk.CTkLabel(
            frame,
            text=subtitle,
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            anchor="w",
        ).grid(row=1, column=1, sticky="w", padx=(8, 0))

    def _policy_separator(self, parent, row):
        sep = ctk.CTkFrame(parent, fg_color=BORDER, height=1)
        sep.grid(row=row, column=0, sticky="ew", padx=20)

    def _update_datetime(self):
        """Update the datetime label every second."""
        try:
            if self._is_destroyed:
                return
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo("Africa/Johannesburg"))
            self._datetime_label.configure(
                text=f"📅  {now.strftime('%A, %d %B %Y')}   |   🕐  {now.strftime('%H:%M:%S')} SAST"
            )
            self.after(1000, self._update_datetime)
        except Exception:
            pass

    def _selected_employee(self):
        if self.employee_menu is not None:
            return self._employees_by_name.get(self.employee_menu.get())
        return None

    def _employee_identity(self):
        return getattr(self._account, "employee_id", None), getattr(self._account, "full_name", "")

    # ------------------------------------------------------------------
    # Backend threading
    # ------------------------------------------------------------------

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
        if self._is_destroyed:
            return

        if self._mongo is None:
            try:
                self.error_label.configure(
                    text="⚠️ Attendance service not connected (mongo_attendance missing)."
                )
            except Exception:
                pass
            return

        if self._sync_inflight:
            return

        employee_id, _ = self._employee_identity()
        if employee_id is None:
            try:
                self.error_label.configure(
                    text="⚠️ No employee_id on this account – cannot sync attendance."
                )
            except Exception:
                pass
            self._schedule_backend_sync(5000)
            return

        self._sync_inflight = True

        self._run_backend(
            lambda: self._mongo.refresh_state(employee_id),
            self._accept_backend_state,
            "Attendance sync",
        )

        self._schedule_backend_sync(
            (self._backend_refresh_seconds * 1000) if delay is None else delay
        )

    def _accept_backend_state(self, state):
        if self._is_destroyed:
            return

        self._hide_loading()
        self._sync_inflight = False
        self._timer_state = dict(state or {})
        # Prefer the record from this payload; never wipe an active session with None
        incoming = self._timer_state.get("record")
        if incoming is not None:
            self._timer_record = incoming
        self._last_update_time = datetime.now().timestamp()
        self._retry_count = 0

        employee_id, _ = self._employee_identity()
        self._render(
            self._timer_record,
            self._timer_state,
            employee_id,
        )

        if employee_id is not None:
            self._update_supporting_data(employee_id)

        try:
            self.error_label.configure(text="")
        except Exception:
            pass

    def _backend_error(self, exc, action_name="attendance"):
        self._hide_loading()
        self._sync_inflight = False
        self._action_inflight = False
        self._retry_count += 1
        print(f"⚠️ {action_name} error: {exc}")

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
        if force:
            self._show_loading("Refreshing attendance…")
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
        if self._is_destroyed:
            return

        # Mirror TimerWidget._render_state exactly so both clocks stay in lock-step
        state = self._timer_state or {
            "state": "not_started",
            "status": "not_started",
            "record": None,
        }
        current_state = state.get("state", "not_started")
        current_status = state.get("status", "clocked_out")
        record = self._timer_record if self._timer_record is not None else state.get("record")

        try:
            if current_state == "working" or current_status == "clocked_in":
                elapsed = (
                    self._mongo.get_live_seconds(record) if self._mongo else 0
                )
            elif current_state == "on_break" or current_status == "on_break":
                elapsed = (
                    self._mongo.get_live_seconds(record) if self._mongo else 0
                )
            elif current_state == "completed" or current_status == "clocked_out":
                if record and isinstance(record, dict):
                    try:
                        elapsed = int(float(record.get("hours_worked") or 0) * 3600)
                    except (TypeError, ValueError):
                        elapsed = 0
                else:
                    elapsed = 0
            else:
                elapsed = 0

            self.timer_label.configure(text=self._format_seconds(elapsed))
        except Exception as exc:
            print(f"⚠️ Timer render error: {exc}")

    @ui_task
    def _update_supporting_data(self, employee_id):
        """Fetch supporting data in workers; render a consistent local snapshot."""
        try:
            self._history_records = yield RemoteCall(self._mongo.get_weekly_timesheet, employee_id)
            self._weekly_total = sum(float(r.get('hours_worked') or 0) for r in self._history_records)
            self._monthly_total = yield RemoteCall(self._mongo.get_monthly_total, employee_id)
        except Exception as exc:
            self._backend_error(exc, 'Attendance history')
            return
        self._render_totals()
        self._render_calendar(employee_id)
        self._render_history(employee_id)
        if self._can_manage:
            try:
                team_records = yield RemoteCall(self._controller.get_team_today)
                working = yield RemoteCall(self._controller.get_working_now)
                self._render_team_attendance(team_records or [], working or {})
            except Exception as exc:
                self._backend_error(exc, 'Team attendance')

    def _render_team_attendance(self, records, working):
        if self.team_frame is None or self.team_summary_label is None:
            return
        for child in self.team_frame.winfo_children():
            child.destroy()
        active_count = int((working or {}).get("count") or 0)
        break_count = int((working or {}).get("on_break_count") or 0)
        self.team_summary_label.configure(
            text=f"{active_count} working  •  {break_count} on break  •  {len(records)} record(s) today"
        )
        if not records:
            ctk.CTkLabel(
                self.team_frame, text="No team attendance recorded today.",
                text_color=MUTED, font=ctk.CTkFont(size=12),
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return
        for row, record in enumerate(records):
            status = str(record.get("status") or "not_started")
            label = {
                "clocked_in": "Working",
                "on_break": "On break",
                "clocked_out": "Clocked out",
            }.get(status, status.replace("_", " ").title())
            line = ctk.CTkFrame(self.team_frame, fg_color="#F8FAFC", corner_radius=8)
            line.grid(row=row, column=0, sticky="ew", padx=4, pady=3)
            line.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                line, text=record.get("employee_name") or "Employee", text_color=TEXT,
                font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=10, pady=(7, 0))
            ctk.CTkLabel(
                line,
                text=f"{self._time(record.get('clock_in_at'))} – {self._time(record.get('clock_out_at'))}",
                text_color=MUTED, font=ctk.CTkFont(size=10), anchor="w",
            ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 7))
            ctk.CTkLabel(
                line, text=label, text_color=ORANGE if status == "on_break" else PRIMARY,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=1, rowspan=2, padx=10)

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
        """Render cached state only. No network I/O happens here.

        State handling mirrors MainWindow.TimerWidget so both timers stay in sync.
        """
        if self._is_destroyed:
            return

        # Keep the authoritative state + active record (do not clear while clocked in)
        self._timer_state = dict(timer or {})
        if record is not None:
            self._timer_record = record
        elif self._timer_state.get("record") is not None:
            self._timer_record = self._timer_state.get("record")
        # else: leave existing self._timer_record alone

        state = self._timer_state or {}
        current_state = str(state.get("state") or "not_started").lower().replace(" ", "_")
        current_status = str(state.get("status") or "clocked_out").lower().replace(" ", "_")
        break_minutes = int(state.get("break_minutes", 0) or 0)

        rec_probe = self._timer_record if isinstance(self._timer_record, dict) else {}
        has_in = bool(rec_probe.get("clock_in_at") or rec_probe.get("started_at"))
        has_out = bool(rec_probe.get("clock_out_at"))
        # Active break: started_at set and either no end, or start is after last end
        _bs = rec_probe.get("break_started_at")
        _be = rec_probe.get("break_ended_at")
        if _bs and has_in and not has_out:
            if not _be:
                on_break_flag = True
            else:
                try:
                    on_break_flag = str(_bs) > str(_be)
                except Exception:
                    on_break_flag = current_status in ("on_break", "break")
        else:
            on_break_flag = False

        # Normalize into the same buckets TimerWidget uses; also trust the record
        if (
            current_state in ("working", "clocked_in")
            or current_status in ("clocked_in", "working", "in", "active")
            or (has_in and not has_out and not on_break_flag)
        ):
            phase = "clocked_in"
        elif (
            current_state == "on_break"
            or current_status in ("on_break", "break")
            or on_break_flag
        ):
            phase = "on_break"
        elif (
            (has_in and has_out)
            or (
                (current_state in ("completed", "clocked_out")
                 or current_status in ("clocked_out", "completed", "out"))
                and has_in
            )
        ):
            phase = "clocked_out"
        else:
            # No real open/closed session for today → treat as not started
            # (fixes API fallback that used to report clocked_out with no record)
            phase = "not_started"

        phase_display = {
            "not_started": ("Not started", "#757575"),
            "clocked_in": ("You are clocked in", PRIMARY),
            "on_break": ("On break", ORANGE),
            "clocked_out": ("Clocked out", "#9E9E9E"),
        }
        display_text, dot_color = phase_display[phase]

        self._status_dot.configure(text_color=dot_color)
        self._status_dot_label.configure(text=display_text)

        self._render_live_timer()

        rec = self._timer_record if isinstance(self._timer_record, dict) else {}
        since_text = ""
        clock_in = rec.get("clock_in_at") if rec else None
        if clock_in:
            since_text = f"Since {self._time(clock_in)}"

        if phase == "not_started":
            self.status_label.configure(text="⏳  Not clocked in today")
            self._since_label.configure(text="")
            try:
                self._banner.configure(fg_color="#F8FAFC", border_color=BORDER)
            except Exception:
                pass
        elif phase == "on_break":
            self.status_label.configure(text=f"☕  On break  •  {break_minutes} min today")
            self._since_label.configure(text=since_text)
            try:
                self._banner.configure(fg_color="#FFFBEB", border_color="#FDE68A")
            except Exception:
                pass
        elif phase == "clocked_out":
            try:
                hours = float(rec.get("hours_worked", 0) or 0) if rec else 0
            except (TypeError, ValueError):
                hours = 0
            self.status_label.configure(text=f"✅  Shift completed  •  {hours:.2f} hours")
            self._since_label.configure(text=since_text)
            try:
                self._banner.configure(fg_color="#F8FAFC", border_color=BORDER)
            except Exception:
                pass
        else:  # clocked_in / working
            self.status_label.configure(text="●  Currently Clocked In")
            self._since_label.configure(text=since_text or f"☕ {break_minutes} min break")
            try:
                self._banner.configure(fg_color=SOFT_BANNER, border_color=SOFT_BANNER_BORDER)
            except Exception:
                pass

        # Today's Summary values
        if rec:
            tin = self._time(rec.get("clock_in_at"))
            tout = self._time(rec.get("clock_out_at"))
            brk = int(rec.get("break_duration_minutes", 0) or break_minutes or 0)
            brk_txt = f"{brk} min" if brk else "—"
        else:
            tin, tout, brk_txt = "—", "—", "—"

        try:
            self._summary_time_in.configure(text=tin)
            self._summary_time_out.configure(text=tout)
            self._summary_break.configure(text=brk_txt)
        except Exception:
            pass

        # Button enablement:
        # - Clock In: allowed only before today's attendance has started
        # - Clock Out: only while actively clocked in
        # - Start Break / End Break: only in matching active phase
        self._set_actions(
            "normal" if phase == "not_started" else "disabled",
            "normal" if phase == "clocked_in" else "disabled",
            "normal" if phase == "clocked_in" else "disabled",
            "normal" if phase == "on_break" else "disabled",
        )

    @staticmethod
    def _punctuality(record) -> tuple:
        """Return status, emoji and label for the 08:00-09:00 SA policy."""
        from zoneinfo import ZoneInfo
        from datetime import time as dtime

        if not record:
            return "absent", "⚫", "Absent"
        clock_in = record.get("clock_in_at") if isinstance(record, dict) else getattr(record, "clock_in_at", None)
        if not clock_in:
            return "absent", "⚫", "Absent"

        sa = ZoneInfo("Africa/Johannesburg")
        utc = ZoneInfo("UTC")
        local = None
        try:
            if isinstance(clock_in, datetime):
                local = clock_in if clock_in.tzinfo else clock_in.replace(tzinfo=utc)
                local = local.astimezone(sa)
            else:
                s = str(clock_in).strip().replace("Z", "+00:00")
                if "T" in s:
                    local = datetime.fromisoformat(s)
                    if local.tzinfo is None:
                        local = local.replace(tzinfo=utc)
                    local = local.astimezone(sa)
                else:
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                        try:
                            local = datetime.strptime(s[:19], fmt).replace(tzinfo=utc).astimezone(sa)
                            break
                        except ValueError:
                            continue
        except Exception:
            local = None

        if local is None:
            return "unknown", "⚪", "Unknown"

        t = local.time()
        # Policy: working hours 09:00 AM – 04:00 PM
        if t < dtime(8, 45, 0):
            return "early", "🟡", "Early"
        if t <= dtime(9, 0, 0):
            return "on_time", "🟢", "On Time"
        return "late", "🔴", "Late"

    def _render_calendar(self, employee_id):
        """Kept for API compatibility (calendar not shown in mockup layout)."""
        if self._is_destroyed:
            return
        try:
            for child in self.calendar_frame.winfo_children():
                child.destroy()
        except Exception:
            pass
        try:
            _ = getattr(self, '_history_records', [])
        except Exception as e:
            print(f"⚠️ Error loading calendar: {e}")

    def _render_history(self, employee_id):
        """Render Recent Activity as a vertical timeline."""
        if self._is_destroyed:
            return

        for child in self.history_frame.winfo_children():
            child.destroy()

        try:
            records = getattr(self, '_history_records', [])
        except Exception as e:
            print(f"⚠️ Error loading history: {e}")
            records = []

        events = []
        for record in records or []:
            if not isinstance(record, dict):
                continue
            date = record.get("work_date", "—")
            punctuality, _emoji, punctuality_label = self._punctuality(record)

            if record.get("clock_in_at"):
                events.append({
                    "title": "Clocked In",
                    "when": f"{date} at {self._time(record.get('clock_in_at'))}",
                    "badge": punctuality_label,
                    "kind": punctuality,
                    "sort": str(record.get("clock_in_at") or ""),
                })
            if record.get("clock_out_at"):
                events.append({
                    "title": "Clocked Out",
                    "when": f"{date} at {self._time(record.get('clock_out_at'))}",
                    "badge": "Normal",
                    "kind": "normal",
                    "sort": str(record.get("clock_out_at") or ""),
                })

            breaks = record.get("breaks") or []
            if isinstance(breaks, list):
                for b in breaks:
                    if not isinstance(b, dict):
                        continue
                    if b.get("start"):
                        events.append({
                            "title": "Break Started",
                            "when": f"{date} at {self._time(b.get('start'))}",
                            "badge": "Normal",
                            "kind": "normal",
                            "sort": str(b.get("start") or ""),
                        })
                    if b.get("end"):
                        events.append({
                            "title": "Break Ended",
                            "when": f"{date} at {self._time(b.get('end'))}",
                            "badge": "Normal",
                            "kind": "normal",
                            "sort": str(b.get("end") or ""),
                        })

        events.sort(key=lambda e: e.get("sort") or "", reverse=True)

        if not events:
            empty = ctk.CTkFrame(self.history_frame, fg_color="transparent")
            empty.grid(row=0, column=0, sticky="nsew", pady=20)
            ctk.CTkLabel(
                empty,
                text="📭  No recent activity this week",
                font=ctk.CTkFont(size=13),
                text_color=MUTED,
            ).pack()
            return

        badge_styles = {
            "on_time": (PRIMARY, "#DCFCE7"),
            "early": (ORANGE, "#FEF3C7"),
            "late": (RED, "#FEE2E2"),
            "normal": (MUTED, "#F1F5F9"),
            "absent": (MUTED, "#F1F5F9"),
            "unknown": (MUTED, "#F1F5F9"),
        }

        for row_idx, ev in enumerate(events[:20]):
            item = ctk.CTkFrame(self.history_frame, fg_color="transparent")
            item.grid(row=row_idx, column=0, sticky="ew", pady=5)
            item.grid_columnconfigure(1, weight=1)

            kind = ev.get("kind", "normal")
            dot_color = {
                "on_time": PRIMARY,
                "early": ORANGE,
                "late": RED,
                "normal": "#94A3B8",
                "absent": "#94A3B8",
            }.get(kind, "#94A3B8")

            ctk.CTkLabel(
                item,
                text="●",
                font=ctk.CTkFont(size=11),
                text_color=dot_color,
                width=18,
            ).grid(row=0, column=0, rowspan=2, sticky="n", pady=(4, 0))

            ctk.CTkLabel(
                item,
                text=ev["title"],
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=TEXT,
                anchor="w",
            ).grid(row=0, column=1, sticky="w", padx=(4, 8))

            ctk.CTkLabel(
                item,
                text=ev["when"],
                font=ctk.CTkFont(size=11),
                text_color=MUTED,
                anchor="w",
            ).grid(row=1, column=1, sticky="w", padx=(4, 8), pady=(0, 2))

            badge_text = ev.get("badge") or "Normal"
            style_key = kind if kind in badge_styles else "normal"
            if badge_text == "On Time":
                style_key = "on_time"
            elif badge_text == "Late":
                style_key = "late"
            elif badge_text == "Early":
                style_key = "early"

            fg, bg = badge_styles.get(style_key, badge_styles["normal"])
            badge = ctk.CTkLabel(
                item,
                text=badge_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=fg,
                fg_color=bg,
                corner_radius=10,
                padx=10,
                pady=3,
            )
            badge.grid(row=0, column=2, rowspan=2, sticky="e", padx=(4, 6))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

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

        # Match MainWindow.TimerWidget signatures exactly (employee_id only).
        def _clock_in_op():
            try:
                return self._mongo.clock_in(employee_id, employee_name)
            except TypeError:
                return self._mongo.clock_in(employee_id)

        action_map = {
            "clock_in": (_clock_in_op, "Clock in"),
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
        self._show_loading(f"{action_name}…")

        self._run_backend(
            operation,
            lambda result: self._accept_action_result(result),
            action_name,
        )

    def _accept_action_result(self, result):
        if self._is_destroyed:
            return

        self._hide_loading()
        self._action_inflight = False
        self._timer_state = dict(result or {})
        incoming = self._timer_state.get("record")
        if incoming is not None:
            self._timer_record = incoming

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
        # Same implementation as MainWindow.TimerWidget
        try:
            total_seconds = max(0, int(float(seconds or 0)))
        except (TypeError, ValueError):
            total_seconds = 0
        return (
            f"{total_seconds // 3600:02d}:"
            f"{(total_seconds % 3600) // 60:02d}:"
            f"{total_seconds % 60:02d}"
        )

    def _time(self, value):
        return self._mongo.format_local_time(value) if self._mongo else "—"

    def destroy(self):
        self._is_destroyed = True
        self._loading_visible = False
        if getattr(self, "_spin_job", None) is not None:
            try:
                self.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None

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
