# app/views/dashboard_view.py
"""
Untangled Nexus – Modern role-aware Dashboard (Employee + Executive).

Business metrics are rendered ONLY from DashboardController.get_summary()
→ Backend API. Missing values are shown as unavailable ("—" / "No data").
Explicit backend zeros are shown as 0. No demo / fake / guessed numbers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import queue
import threading
import time

import customtkinter as ctk

from app.controllers.dashboard_controller import DashboardController
from app.utils.theme import Theme


# ── Design tokens ──────────────────────────────────────────────────────────
BG = "#F5F7FA"
CARD = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#0F172A"
MUTED = "#64748B"
GREEN = "#16A34A"
GREEN_SOFT = "#DCFCE7"
GREEN_BANNER = "#ECFDF5"
BLUE = "#2563EB"
BLUE_SOFT = "#DBEAFE"
ORANGE = "#F59E0B"
ORANGE_SOFT = "#FEF3C7"
RED = "#DC2626"
RED_SOFT = "#FEE2E2"
PURPLE = "#7C3AED"
PURPLE_SOFT = "#EDE9FE"
CYAN = "#0891B2"
CYAN_SOFT = "#CFFAFE"
GRAY_SOFT = "#F1F5F9"

UNAVAILABLE = "—"


def _v(source: Any, name: str, default: Any = None) -> Any:
    """Safe attribute / dict lookup. Never invents business data."""
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    try:
        return getattr(source, name, default)
    except Exception:
        return default


def _has_value(value: Any) -> bool:
    """True when the backend actually supplied a value (including 0)."""
    return value is not None and value != ""


def _as_int_or_none(value: Any) -> Optional[int]:
    """
    Parse a non-negative int when present.
    Returns None when the backend did not supply a usable value.
    Explicit 0 stays 0.
    """
    if not _has_value(value):
        return None
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return None


def _as_float_or_none(value: Any) -> Optional[float]:
    if not _has_value(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_int(value: Optional[int]) -> str:
    return UNAVAILABLE if value is None else str(value)


def _fmt_pct(value: Optional[int]) -> str:
    return UNAVAILABLE if value is None else f"{value}%"


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _is_executive(role: str) -> bool:
    r = (role or "").lower().replace("_", " ").replace("-", " ")
    return any(
        k in r
        for k in (
            "director",
            "manager",
            "admin",
            "administrator",
            "business lead",
            "executive",
            "operations manager",
        )
    )


def _attendance_block(summary: Any) -> dict:
    """
    Read attendance from canonical places only.
    Supports either flat summary fields or nested summary['attendance'].
    Present is always aligned with people currently working when the backend
    reports people_working / people_on_site.
    Does not invent values beyond that alignment.
    """
    nested = _v(summary, "attendance")
    if not isinstance(nested, dict):
        nested = {}

    people_working = _as_int_or_none(
        _v(summary, "people_working")
        if _has_value(_v(summary, "people_working"))
        else _v(summary, "people_on_site")
    )

    present = _as_int_or_none(
        _v(nested, "present")
        if "present" in nested
        else _v(summary, "present_count")
    )
    # Present must match people currently working (open clock-ins)
    if people_working is not None and (present is None or present != people_working):
        present = people_working

    late = _as_int_or_none(
        _v(nested, "late")
        if "late" in nested
        else _v(summary, "late_count")
    )

    total = _as_int_or_none(
        _v(nested, "total")
        if "total" in nested
        else (
            _v(summary, "attendance_total")
            if _has_value(_v(summary, "attendance_total"))
            else (
                _v(summary, "total_people")
                if _has_value(_v(summary, "total_people"))
                else _v(summary, "total_employees")
            )
        )
    )

    absent = _as_int_or_none(
        _v(nested, "absent")
        if "absent" in nested
        else _v(summary, "absent_count")
    )
    # Keep absent consistent with present/total when both are known
    if total is not None and present is not None:
        absent = max(0, total - present)

    pct = _as_int_or_none(
        _v(nested, "percentage")
        if "percentage" in nested
        else (
            _v(nested, "pct")
            if "pct" in nested
            else _v(summary, "attendance_pct")
        )
    )

    # Only compute percentage when both present and total were supplied
    if present is not None and total is not None and total > 0:
        pct = int(round((present / total) * 100))

    return {
        "present": present,
        "absent": absent,
        "late": late,
        "total": total,
        "percentage": pct,
    }


class DashboardView(ctk.CTkFrame):
    """Role-aware modern dashboard (Employee or Executive). Real data only."""

    REFRESH_INTERVAL_MS = 60_000
    OUTER_PAD = 20

    def __init__(self, master, controller: DashboardController) -> None:
        super().__init__(master, fg_color=BG, corner_radius=0)

        self._controller = controller
        self._refresh_job: Optional[str] = None
        self._queue_job: Optional[str] = None
        self._is_destroyed = False
        self._refresh_running = False
        self._last_refresh_started = 0.0
        self._backend_queue: queue.Queue = queue.Queue()
        self._summary: Any = None
        self._last_error: Optional[str] = None

        self._account = self._find_current_account()
        self._navigation_controller = self._find_navigation_controller()
        role = str(_v(self._account, "role", "Employee") or "Employee")
        self._executive = _is_executive(role)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=GRAY_SOFT,
            scrollbar_button_hover_color=BORDER,
        )
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)

        # Error banner (hidden until an API failure)
        self._error_banner = ctk.CTkFrame(
            self.content, fg_color=RED_SOFT, corner_radius=12, border_width=1, border_color=RED
        )
        self._error_banner.grid(row=0, column=0, sticky="ew", padx=self.OUTER_PAD, pady=(12, 0))
        self._error_banner.grid_remove()
        self._error_label = ctk.CTkLabel(
            self._error_banner,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=RED,
            anchor="w",
            wraplength=700,
        )
        self._error_label.pack(side="left", padx=14, pady=10, fill="x", expand=True)
        ctk.CTkButton(
            self._error_banner,
            text="Retry",
            width=80,
            height=28,
            fg_color=RED,
            hover_color="#B91C1C",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._safe_refresh,
        ).pack(side="right", padx=12, pady=8)

        if self._executive:
            self._build_executive()
            self._apply_executive(None)
        else:
            self._build_employee()

        self._queue_job = self.after(50, self._drain_backend_queue)
        self.after(150, self._safe_refresh)
        self._refresh_job = self.after(self.REFRESH_INTERVAL_MS, self._scheduled_refresh)

    # ==================================================================
    # Discovery
    # ==================================================================

    def _find_main_window(self):
        widget = self.master
        while widget is not None:
            try:
                if hasattr(widget, "_current_account"):
                    return widget
            except Exception:
                pass
            try:
                widget = widget.master
            except Exception:
                break
        return None

    def _find_current_account(self):
        mw = self._find_main_window()
        return getattr(mw, "_current_account", None) if mw else None

    def _find_navigation_controller(self):
        mw = self._find_main_window()
        return getattr(mw, "_navigation_controller", None) if mw else None

    def _navigate(self, destination: str) -> None:
        nav = self._navigation_controller
        if nav is None:
            print(f"⚠️ Dashboard navigation unavailable: {destination}")
            return
        try:
            nav.navigate(destination)
        except Exception as exc:
            print(f"⚠️ Dashboard navigation error for {destination}: {exc}")

    # ==================================================================
    # Shared helpers
    # ==================================================================

    def _card(self, parent, title: str, link: str = "", dest: str = "") -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER
        )
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text=title, font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT, anchor="w"
        ).grid(row=0, column=0, sticky="w")
        if link and dest:
            ctk.CTkButton(
                header,
                text=link,
                width=70,
                height=26,
                corner_radius=8,
                fg_color="transparent",
                hover_color=GRAY_SOFT,
                text_color=GREEN,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda d=dest: self._navigate(d),
            ).grid(row=0, column=1, sticky="e")
        return card

    def _tick_clock(self) -> None:
        if self._is_destroyed:
            return
        try:
            now = datetime.now()
            if hasattr(self, "date_label"):
                self.date_label.configure(text=f"🕐  {now.strftime('%H:%M:%S')} SAST")
            self.after(1000, self._tick_clock)
        except Exception:
            pass

    def _show_error(self, message: str) -> None:
        self._last_error = message
        try:
            self._error_label.configure(text=f"Unable to load dashboard data: {message}")
            self._error_banner.grid()
        except Exception:
            pass

    def _clear_error(self) -> None:
        self._last_error = None
        try:
            self._error_banner.grid_remove()
        except Exception:
            pass

    # ==================================================================
    # EMPLOYEE LAYOUT (compact)
    # ==================================================================

    def _build_employee(self) -> None:
        self._build_welcome_banner(executive=False)
        row = ctk.CTkFrame(self.content, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=self.OUTER_PAD, pady=(0, 14))
        for i in range(4):
            row.grid_columnconfigure(i, weight=1, uniform="ekpi")
        self.emp_kpi = {}
        for i, (key, icon, color, soft, title, value, sub) in enumerate(
            [
                ("tasks", "📋", BLUE, BLUE_SOFT, "My Tasks", UNAVAILABLE, ""),
                ("hours", "⏱", GREEN, GREEN_SOFT, "Hours Worked Today", UNAVAILABLE, ""),
                ("leave", "🏝", ORANGE, ORANGE_SOFT, "Leave Balance", UNAVAILABLE, "remaining"),
                ("attendance", "✓", GREEN, GREEN_SOFT, "Attendance Status", UNAVAILABLE, ""),
            ]
        ):
            card = ctk.CTkFrame(
                row, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER
            )
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0 if i == 3 else 6))
            badge = ctk.CTkFrame(card, width=40, height=40, corner_radius=12, fg_color=soft)
            badge.grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=14)
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=icon, font=ctk.CTkFont(size=16), text_color=color).place(
                relx=0.5, rely=0.5, anchor="center"
            )
            ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=12), text_color=MUTED, anchor="w"
            ).grid(row=0, column=1, sticky="sw", pady=(14, 0))
            val = ctk.CTkLabel(
                card, text=value, font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT, anchor="w"
            )
            val.grid(row=1, column=1, sticky="nw")
            sub_l = ctk.CTkLabel(
                card, text=sub, font=ctk.CTkFont(size=11), text_color=MUTED, anchor="w"
            )
            sub_l.grid(row=2, column=1, sticky="nw", pady=(0, 14))
            self.emp_kpi[key] = (val, sub_l)

        qa = self._card(self.content, "⚡  Quick Actions")
        qa.grid(row=2, column=0, sticky="ew", padx=self.OUTER_PAD, pady=(0, 20))
        btns = ctk.CTkFrame(qa, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 14))
        for i in range(4):
            btns.grid_columnconfigure(i, weight=1)
        for i, (label, color, dest) in enumerate(
            [
                ("Tasks", GREEN, "Tasks"),
                ("Attendance", BLUE, "Attendance"),
                ("Calendar", ORANGE, "Calendar"),
                ("Notifications", PURPLE, "Notifications"),
            ]
        ):
            ctk.CTkButton(
                btns,
                text=label,
                height=40,
                corner_radius=12,
                fg_color=color,
                hover_color=color,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda d=dest: self._navigate(d),
            ).grid(row=0, column=i, sticky="ew", padx=4)

    def _build_welcome_banner(self, executive: bool) -> None:
        banner = ctk.CTkFrame(
            self.content,
            fg_color=GREEN_BANNER,
            corner_radius=16,
            border_width=1,
            border_color="#BBF7D0",
        )
        banner.grid(row=1, column=0, sticky="ew", padx=self.OUTER_PAD, pady=(16, 12))
        banner.grid_columnconfigure(1, weight=1)

        name = str(_v(self._account, "full_name", "there") or "there")
        av = ctk.CTkFrame(banner, width=48, height=48, corner_radius=24, fg_color=GREEN)
        av.grid(row=0, column=0, padx=(18, 12), pady=16)
        av.pack_propagate(False)
        ctk.CTkLabel(
            av, text=_initials(name), font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF"
        ).place(relx=0.5, rely=0.5, anchor="center")

        mid = ctk.CTkFrame(banner, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="w", pady=16)
        hour = datetime.now().hour
        greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        self.greeting_label = ctk.CTkLabel(
            mid,
            text=f"{greet}, {name}!",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT,
            anchor="w",
        )
        self.greeting_label.pack(anchor="w")
        sub = (
            "Here's your executive overview of today's business operations."
            if executive
            else "Here's your workspace overview for today."
        )
        self.welcome_subtitle = ctk.CTkLabel(
            mid, text=sub, font=ctk.CTkFont(size=13), text_color=MUTED, anchor="w"
        )
        self.welcome_subtitle.pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(banner, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=18, pady=16)
        now = datetime.now()
        self.day_label = ctk.CTkLabel(
            right,
            text=f"📅  {now.strftime('%A, %d %B %Y')}",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            anchor="e",
        )
        self.day_label.pack(anchor="e")
        self.date_label = ctk.CTkLabel(
            right,
            text=f"🕐  {now.strftime('%H:%M:%S')} SAST",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            anchor="e",
        )
        self.date_label.pack(anchor="e", pady=(4, 0))
        self.after(1000, self._tick_clock)

    # ==================================================================
    # EXECUTIVE LAYOUT
    # ==================================================================

    def _build_executive(self) -> None:
        self._build_welcome_banner(executive=True)
        self._build_exec_kpis()
        self._build_exec_middle()
        self._build_exec_bottom()

    def _build_exec_kpis(self) -> None:
        row = ctk.CTkFrame(self.content, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=self.OUTER_PAD, pady=(0, 12))
        for i in range(5):
            row.grid_columnconfigure(i, weight=1, uniform="xkpi")

        self.exec_kpi = {}
        # Initial state = unavailable, never fake business numbers
        specs = [
            ("people", "👥", GREEN, GREEN_SOFT, "People Working", f"{UNAVAILABLE} / {UNAVAILABLE}", ""),
            ("attendance", "⏱", BLUE, BLUE_SOFT, "Attendance Today", UNAVAILABLE, "No data"),
            ("due", "☰", ORANGE, ORANGE_SOFT, "Tasks Due Today", UNAVAILABLE, ""),
            ("approvals", "⏳", PURPLE, PURPLE_SOFT, "Pending Approvals", UNAVAILABLE, ""),
            ("revenue", "📈", CYAN, CYAN_SOFT, "Revenue Snapshot", UNAVAILABLE, "No revenue data"),
        ]
        for i, (key, icon, color, soft, title, value, sub) in enumerate(specs):
            card = ctk.CTkFrame(
                row, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER
            )
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 5, 0 if i == 4 else 5))
            card.grid_columnconfigure(1, weight=1)

            badge = ctk.CTkFrame(card, width=42, height=42, corner_radius=21, fg_color=soft)
            badge.grid(row=0, column=0, rowspan=3, padx=(12, 8), pady=12)
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=icon, font=ctk.CTkFont(size=15), text_color=color).place(
                relx=0.5, rely=0.5, anchor="center"
            )
            ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=11), text_color=MUTED, anchor="w"
            ).grid(row=0, column=1, sticky="sw", pady=(10, 0), padx=(0, 10))
            val = ctk.CTkLabel(
                card, text=value, font=ctk.CTkFont(size=20, weight="bold"), text_color=TEXT, anchor="w"
            )
            val.grid(row=1, column=1, sticky="nw", padx=(0, 10))
            sub_l = ctk.CTkLabel(
                card, text=sub, font=ctk.CTkFont(size=10), text_color=MUTED, anchor="w"
            )
            sub_l.grid(row=2, column=1, sticky="nw", pady=(0, 10), padx=(0, 10))
            self.exec_kpi[key] = (val, sub_l)

    def _build_exec_middle(self) -> None:
        mid = ctk.CTkFrame(self.content, fg_color="transparent")
        mid.grid(row=3, column=0, sticky="ew", padx=self.OUTER_PAD, pady=(0, 10))
        mid.grid_columnconfigure(0, weight=65)
        mid.grid_columnconfigure(1, weight=35)

        left = ctk.CTkFrame(mid, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)

        # Department Performance
        dept = self._card(left, "📊  Department Performance")
        dept.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        legend = ctk.CTkFrame(dept, fg_color="transparent")
        legend.pack(fill="x", padx=16, pady=(0, 2))
        for label, color in [("Completed", GREEN), ("In Progress", BLUE), ("Overdue", ORANGE)]:
            ctk.CTkLabel(
                legend, text=f"●  {label}", font=ctk.CTkFont(size=11), text_color=color
            ).pack(side="left", padx=(0, 12))
        self.dept_frame = ctk.CTkFrame(dept, fg_color="transparent", height=150)
        self.dept_frame.pack(fill="x", padx=12, pady=(4, 14))
        self.dept_frame.pack_propagate(False)
        self._render_departments(None)

        # Activity table
        act = self._card(left, "📋  Recent Operational Activity", link="View all", dest="Notifications")
        act.grid(row=1, column=0, sticky="ew")
        hdr = ctk.CTkFrame(act, fg_color=GRAY_SOFT, corner_radius=8)
        hdr.pack(fill="x", padx=12, pady=(0, 2))
        for col, w in [("#", 28), ("Employee", 110), ("Department", 90), ("Activity", 260), ("Time", 70)]:
            ctk.CTkLabel(
                hdr, text=col, font=ctk.CTkFont(size=11, weight="bold"), text_color=MUTED, width=w, anchor="w"
            ).pack(side="left", padx=4, pady=6)
        self.exec_activity = ctk.CTkFrame(act, fg_color="transparent")
        self.exec_activity.pack(fill="x", padx=12, pady=(2, 12))
        self._render_activity_rows(None)

        # RIGHT column
        right = ctk.CTkFrame(mid, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)

        # Attendance overview
        att = self._card(right, "◎  Team Attendance Overview", link="View all", dest="Attendance")
        att.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        body = ctk.CTkFrame(att, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(0, 12))
        body.grid_columnconfigure(1, weight=1)

        ring = ctk.CTkFrame(
            body, width=120, height=120, corner_radius=60,
            fg_color=GREEN_SOFT, border_width=12, border_color=GREEN,
        )
        ring.grid(row=0, column=0, padx=(8, 12), pady=8)
        ring.pack_propagate(False)
        self.att_pct_label = ctk.CTkLabel(
            ring, text=UNAVAILABLE, font=ctk.CTkFont(size=26, weight="bold"), text_color=GREEN
        )
        self.att_pct_label.place(relx=0.5, rely=0.42, anchor="center")
        self.att_sub_label = ctk.CTkLabel(
            ring, text="No attendance data", font=ctk.CTkFont(size=11), text_color=MUTED
        )
        self.att_sub_label.place(relx=0.5, rely=0.65, anchor="center")

        legend2 = ctk.CTkFrame(body, fg_color="transparent")
        legend2.grid(row=0, column=1, sticky="w")
        self.att_legend = {}
        for key, label, color in [
            ("present", "Present", GREEN),
            ("absent", "Absent", RED),
            ("late", "Late", ORANGE),
        ]:
            r = ctk.CTkFrame(legend2, fg_color="transparent")
            r.pack(anchor="w", pady=4)
            ctk.CTkLabel(r, text="●", text_color=color, font=ctk.CTkFont(size=13), width=16).pack(
                side="left"
            )
            ctk.CTkLabel(
                r, text=label, text_color=MUTED, font=ctk.CTkFont(size=12), width=60, anchor="w"
            ).pack(side="left")
            count_l = ctk.CTkLabel(
                r, text=UNAVAILABLE, text_color=TEXT, font=ctk.CTkFont(size=13, weight="bold")
            )
            count_l.pack(side="left", padx=(6, 0))
            self.att_legend[key] = count_l

        # Approvals queue
        appr = self._card(right, "📋  Approvals Queue", link="View all", dest="Approvals")
        appr.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.approvals_list = ctk.CTkFrame(appr, fg_color="transparent")
        self.approvals_list.pack(fill="x", padx=10, pady=(0, 12))
        self._render_approvals(None)

        # Quick actions
        qa = self._card(right, "⚡  Quick Actions")
        qa.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        grid = ctk.CTkFrame(qa, fg_color="transparent")
        grid.pack(fill="x", padx=10, pady=(0, 12))
        for i in range(2):
            grid.grid_columnconfigure(i, weight=1)
        for i, (label, sub, color, dest) in enumerate(
            [
                ("📊  View Reports", "Analytics & insights", GREEN, "Reports"),
                ("👥  Manage Team", "Users & permissions", BLUE, "People"),
                ("✓  Approve Requests", "Review & approve", ORANGE, "Approvals"),
                ("＋  Create Project", "New project setup", PURPLE, "Projects"),
            ]
        ):
            r, c = divmod(i, 2)
            btn = ctk.CTkButton(
                grid,
                text=f"{label}\n{sub}",
                height=56,
                corner_radius=12,
                fg_color=color,
                hover_color=color,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda d=dest: self._navigate(d),
            )
            btn.grid(row=r, column=c, sticky="ew", padx=4, pady=4)

        # System status (static UI labels only)
        sys_card = self._card(right, "🛡  System Status")
        sys_card.grid(row=3, column=0, sticky="ew")
        sys_row = ctk.CTkFrame(sys_card, fg_color="transparent")
        sys_row.pack(fill="x", padx=10, pady=(0, 12))
        for i in range(2):
            sys_row.grid_columnconfigure(i, weight=1)
        for i, (label, sub) in enumerate(
            [
                ("Server Online", "All systems operational"),
                ("Database", "Healthy"),
                ("Email Service", "Operational"),
                ("File Storage", "Healthy"),
            ]
        ):
            r, c = divmod(i, 2)
            cell = ctk.CTkFrame(sys_row, fg_color=GRAY_SOFT, corner_radius=10)
            cell.grid(row=r, column=c, sticky="ew", padx=3, pady=3)
            ctk.CTkLabel(
                cell, text=f"●  {label}", font=ctk.CTkFont(size=11, weight="bold"),
                text_color=GREEN, anchor="w"
            ).pack(anchor="w", padx=8, pady=(6, 0))
            ctk.CTkLabel(
                cell, text=sub, font=ctk.CTkFont(size=10), text_color=MUTED, anchor="w"
            ).pack(anchor="w", padx=8, pady=(0, 6))

    def _build_exec_bottom(self) -> None:
        pass

    def _dept_grouped_bar(self, parent, name: str, completed: int, progress: int, overdue: int) -> None:
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left", fill="both", expand=True, padx=3)
        max_v = max(completed, progress, overdue, 1)
        bars = ctk.CTkFrame(col, fg_color="transparent", height=110)
        bars.pack(fill="x")
        bars.pack_propagate(False)
        inner = ctk.CTkFrame(bars, fg_color="transparent")
        inner.place(relx=0.5, rely=1.0, anchor="s")
        for val, color in [(completed, GREEN), (progress, BLUE), (overdue, ORANGE)]:
            h = max(10, int(95 * val / max_v))
            bar = ctk.CTkFrame(inner, width=16, height=h, corner_radius=4, fg_color=color)
            bar.pack(side="left", padx=2)
            bar.pack_propagate(False)
            ctk.CTkLabel(
                bar, text=str(val), font=ctk.CTkFont(size=8, weight="bold"), text_color="#FFFFFF"
            ).place(relx=0.5, rely=0.08, anchor="n")
        ctk.CTkLabel(
            col, text=name, font=ctk.CTkFont(size=10), text_color=MUTED
        ).pack(pady=(4, 0))

    def _render_departments(self, departments) -> None:
        for w in self.dept_frame.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        if departments is None:
            ctk.CTkLabel(
                self.dept_frame,
                text="No department performance data available.",
                font=ctk.CTkFont(size=12),
                text_color=MUTED,
            ).pack(anchor="w", pady=20, padx=8)
            return
        if not departments:
            ctk.CTkLabel(
                self.dept_frame,
                text="No department performance data available.",
                font=ctk.CTkFont(size=12),
                text_color=MUTED,
            ).pack(anchor="w", pady=20, padx=8)
            return
        for item in list(departments)[:8]:
            if isinstance(item, (list, tuple)) and len(item) >= 4:
                name, completed, progress, overdue = item[0], item[1], item[2], item[3]
            elif isinstance(item, dict):
                name = item.get("name") or item.get("department") or "—"
                completed = _as_int_or_none(item.get("completed") if "completed" in item else item.get("done"))
                progress = _as_int_or_none(
                    item.get("in_progress") if "in_progress" in item else item.get("progress")
                )
                overdue = _as_int_or_none(item.get("overdue"))
                if completed is None or progress is None or overdue is None:
                    continue
            else:
                continue
            self._dept_grouped_bar(
                self.dept_frame,
                str(name),
                completed if completed is not None else 0,
                progress if progress is not None else 0,
                overdue if overdue is not None else 0,
            )

    def _render_approvals(self, items) -> None:
        for w in self.approvals_list.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        if items is None:
            ctk.CTkLabel(
                self.approvals_list,
                text="No approval data available.",
                font=ctk.CTkFont(size=12),
                text_color=MUTED,
            ).pack(anchor="w", pady=8)
            return
        items = list(items or [])
        if not items:
            ctk.CTkLabel(
                self.approvals_list,
                text="No pending approvals.",
                font=ctk.CTkFont(size=12),
                text_color=MUTED,
            ).pack(anchor="w", pady=8)
            return
        for item in items[:5]:
            if isinstance(item, dict):
                title = item.get("type") or item.get("title") or item.get("request_type") or "Request"
                who = item.get("employee") or item.get("name") or item.get("requested_by") or "—"
                when = (
                    item.get("when")
                    or item.get("date")
                    or item.get("submitted_at")
                    or item.get("created_at")
                    or ""
                )
            else:
                title = getattr(item, "title", None) or getattr(item, "request_type", None) or "Request"
                who = getattr(item, "requested_by", None) or "—"
                when = getattr(item, "submitted_at", None) or getattr(item, "created_at", None) or ""
            icon = "✈️" if "leave" in str(title).lower() else "🏢" if "office" in str(title).lower() else "💵"
            card = ctk.CTkFrame(
                self.approvals_list, fg_color=GRAY_SOFT, corner_radius=12,
                border_width=1, border_color=BORDER,
            )
            card.pack(fill="x", pady=3)
            card.grid_columnconfigure(1, weight=1)
            badge = ctk.CTkFrame(card, width=32, height=32, corner_radius=10, fg_color=ORANGE_SOFT)
            badge.grid(row=0, column=0, rowspan=2, padx=8, pady=8)
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=icon, font=ctk.CTkFont(size=12)).place(
                relx=0.5, rely=0.5, anchor="center"
            )
            ctk.CTkLabel(
                card, text=str(title), font=ctk.CTkFont(size=12, weight="bold"),
                text_color=TEXT, anchor="w"
            ).grid(row=0, column=1, sticky="w", pady=(8, 0))
            ctk.CTkLabel(
                card, text=f"{who}  ·  {when}".strip(" ·"),
                font=ctk.CTkFont(size=10), text_color=MUTED, anchor="w"
            ).grid(row=1, column=1, sticky="w", pady=(0, 8))
            ctk.CTkLabel(
                card, text="Pending", font=ctk.CTkFont(size=10, weight="bold"),
                text_color=ORANGE, fg_color=ORANGE_SOFT, corner_radius=8, padx=8, pady=2,
            ).grid(row=0, column=2, rowspan=2, padx=8)

    def _render_activity_rows(self, activities) -> None:
        for w in self.exec_activity.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass
        if activities is None:
            ctk.CTkLabel(
                self.exec_activity, text="No activity data available.",
                font=ctk.CTkFont(size=12), text_color=MUTED
            ).pack(anchor="w", pady=8)
            return
        if not activities:
            ctk.CTkLabel(
                self.exec_activity, text="No recent operational activity.",
                font=ctk.CTkFont(size=12), text_color=MUTED
            ).pack(anchor="w", pady=8)
            return
        for idx, activity in enumerate(list(activities)[:10], start=1):
            who = str(
                _v(activity, "employee")
                or _v(activity, "user")
                or _v(activity, "name")
                or "Team member"
            )
            dept = str(_v(activity, "department") or "—")
            action = self._format_activity_action(activity)
            # Relative time: prefer clock-out moment, else clock-in
            when_raw = (
                _v(activity, "clock_out_at")
                or _v(activity, "created_at")
                or _v(activity, "clock_in_at")
            )
            when = self._format_activity_time(when_raw)
            row = ctk.CTkFrame(self.exec_activity, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=str(idx), font=ctk.CTkFont(size=11), text_color=MUTED, width=28, anchor="w"
            ).pack(side="left", padx=4)
            av = ctk.CTkFrame(row, width=24, height=24, corner_radius=12, fg_color=BLUE_SOFT)
            av.pack(side="left", padx=(0, 6))
            av.pack_propagate(False)
            ctk.CTkLabel(
                av, text=_initials(who), font=ctk.CTkFont(size=9, weight="bold"), text_color=BLUE
            ).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(
                row, text=who[:16], font=ctk.CTkFont(size=12, weight="bold"),
                text_color=TEXT, width=100, anchor="w"
            ).pack(side="left", padx=2)
            ctk.CTkLabel(
                row, text=dept[:12], font=ctk.CTkFont(size=11), text_color=MUTED, width=80, anchor="w"
            ).pack(side="left", padx=2)
            # Wider so "Clocked Out · 17:05 · In 09:29" is not cut off
            ctk.CTkLabel(
                row, text=f"●  {action}", font=ctk.CTkFont(size=11),
                text_color=TEXT, width=250, anchor="w"
            ).pack(side="left", padx=2)
            ctk.CTkLabel(
                row, text=when, font=ctk.CTkFont(size=11), text_color=MUTED, width=70, anchor="e"
            ).pack(side="right", padx=4)

    @staticmethod
    def _hm_sast(value) -> Optional[str]:
        """Format a datetime/ISO value as HH:MM in local display (SAST data)."""
        if not value:
            return None
        try:
            if isinstance(value, datetime):
                dt = value
            else:
                text = str(value).strip()
                if text.endswith("Z"):
                    text = text[:-1] + "+00:00"
                dt = datetime.fromisoformat(text)
            # Prefer explicit timezone conversion when aware
            if dt.tzinfo is not None:
                try:
                    from zoneinfo import ZoneInfo
                    dt = dt.astimezone(ZoneInfo("Africa/Johannesburg"))
                except Exception:
                    pass
            return dt.strftime("%H:%M")
        except Exception:
            return None

    def _format_activity_action(self, activity) -> str:
        """Build In/Out line from fields so clock-out is never hidden."""
        nested = _v(activity, "record")
        if not isinstance(nested, dict):
            nested = {}

        cin = self._hm_sast(
            _v(activity, "clock_in_at")
            or nested.get("clock_in_at")
            or _v(activity, "started_at")
            or _v(activity, "start_time")
        )
        cout = self._hm_sast(
            _v(activity, "clock_out_at")
            or nested.get("clock_out_at")
            or _v(activity, "ended_at")
            or _v(activity, "end_time")
        )
        status = str(
            _v(activity, "status") or _v(activity, "state") or nested.get("status") or ""
        ).strip().lower().replace(" ", "_").replace("-", "_")
        if cout is None and status in ("clocked_out", "completed", "out", "done"):
            cout = self._hm_sast(_v(activity, "updated_at") or nested.get("updated_at"))

        desc = str(_v(activity, "description") or _v(activity, "action") or "")

        if cin and cout:
            return f"Out {cout} · In {cin}"
        if cout:
            return f"Out {cout}"
        if "clocked out" in desc.lower() or desc.lower().startswith("out "):
            return desc[:48]
        if cin:
            if "break" in status:
                return f"On Break · In {cin}"
            if status == "late" or "late" in desc.lower():
                return f"In {cin} · Late · Still in"
            return f"In {cin} · Still in"
        return (desc or "Activity")[:48]

    # ==================================================================
    # Data refresh
    # ==================================================================

    def refresh(self) -> None:
        if not self._is_destroyed:
            self._safe_refresh()

    def _safe_refresh(self) -> None:
        if self._is_destroyed or self._refresh_running:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        now = time.monotonic()
        if now - self._last_refresh_started < 2.0:
            return
        self._refresh_running = True
        self._last_refresh_started = now

        def worker() -> None:
            try:
                summary = self._controller.get_summary()
                self._backend_queue.put((True, summary, None))
            except Exception as exc:
                self._backend_queue.put((False, None, exc))

        threading.Thread(target=worker, daemon=True, name="DashboardAPI").start()

    def _drain_backend_queue(self) -> None:
        if self._is_destroyed:
            return
        try:
            while True:
                success, summary, error = self._backend_queue.get_nowait()
                self._refresh_running = False
                if success:
                    if isinstance(summary, dict) and summary.get("error"):
                        self._show_error(str(summary.get("error")))
                        # Do not invent zeros on partial/error payloads
                        self._apply_summary(summary)
                    else:
                        self._clear_error()
                        self._apply_summary(summary)
                else:
                    print(f"⚠️ Dashboard refresh error: {error}")
                    self._show_error(str(error) if error else "Unknown error")
        except queue.Empty:
            pass
        except Exception as exc:
            self._refresh_running = False
            print(f"⚠️ Dashboard result handling error: {exc}")
        if not self._is_destroyed:
            try:
                self._queue_job = self.after(50, self._drain_backend_queue)
            except Exception:
                self._queue_job = None

    def _apply_summary(self, summary) -> None:
        if self._is_destroyed:
            return
        # Keep previous good data on empty/error payloads so KPIs do not flash "—"
        if summary is None and self._summary is not None:
            return
        if isinstance(summary, dict) and summary.get("error") and self._summary is not None:
            # Still show the error banner, but do not wipe KPIs
            pass
        elif summary is not None:
            self._summary = summary
        try:
            data = self._summary if summary is None else summary
            if isinstance(summary, dict) and summary.get("error") and self._summary is not None:
                data = self._summary
            if self._executive:
                self._apply_executive(data)
            else:
                self._apply_employee(data)
        except Exception as exc:
            print(f"⚠️ Dashboard render error: {exc}")

    def _apply_executive(self, summary) -> None:
        """
        Render only values the backend actually supplied.
        Missing → "—" / "No data". Explicit 0 → "0".
        """
        # ---- People Working (canonical fields only; no wrong OR chains) ----
        people = _as_int_or_none(_v(summary, "people_working"))
        total = _as_int_or_none(_v(summary, "total_people"))
        if total is None:
            # Accept only clearly equivalent total fields if total_people absent
            total = _as_int_or_none(_v(summary, "total_employees"))
        if "people" in self.exec_kpi:
            self.exec_kpi["people"][0].configure(
                text=f"{_fmt_int(people)} / {_fmt_int(total)}"
            )
            self.exec_kpi["people"][1].configure(text="")

        # ---- Attendance (no fake zeros) ----
        att = _attendance_block(summary)
        present, absent, late = att["present"], att["absent"], att["late"]
        att_total = att["total"] if att["total"] is not None else total
        att_pct = att["percentage"]

        if "attendance" in self.exec_kpi:
            self.exec_kpi["attendance"][0].configure(text=_fmt_pct(att_pct))
            if present is None:
                self.exec_kpi["attendance"][1].configure(text="No data")
            else:
                self.exec_kpi["attendance"][1].configure(text=f"{present} Present")

        if hasattr(self, "att_pct_label"):
            self.att_pct_label.configure(text=_fmt_pct(att_pct) if att_pct is not None else UNAVAILABLE)
        if hasattr(self, "att_sub_label"):
            if present is None and att_total is None:
                self.att_sub_label.configure(text="No attendance data")
            else:
                self.att_sub_label.configure(
                    text=f"{_fmt_int(present)} of {_fmt_int(att_total)}"
                )
        if hasattr(self, "att_legend"):
            for key, val in [("present", present), ("absent", absent), ("late", late)]:
                if key in self.att_legend:
                    try:
                        self.att_legend[key].configure(text=_fmt_int(val))
                    except Exception:
                        pass

        # ---- Tasks due today (do NOT substitute overdue for high priority) ----
        tasks_block = _v(summary, "tasks")
        if isinstance(tasks_block, dict):
            due = _as_int_or_none(_v(tasks_block, "due_today"))
            high = _as_int_or_none(_v(tasks_block, "high_priority_due_today"))
        else:
            due = _as_int_or_none(_v(summary, "tasks_due_today"))
            high = _as_int_or_none(_v(summary, "tasks_high_priority"))

        if "due" in self.exec_kpi:
            self.exec_kpi["due"][0].configure(text=_fmt_int(due))
            if high is None:
                self.exec_kpi["due"][1].configure(text="")
            else:
                self.exec_kpi["due"][1].configure(text=f"{high} High Priority")

        # ---- Pending approvals ----
        pending = _as_int_or_none(_v(summary, "pending_approvals"))
        if "approvals" in self.exec_kpi:
            self.exec_kpi["approvals"][0].configure(text=_fmt_int(pending))
            self.exec_kpi["approvals"][1].configure(text="")

        # ---- Revenue: only show R0 when backend explicitly returns 0 ----
        revenue = _v(summary, "revenue")
        if not _has_value(revenue):
            revenue = _v(summary, "revenue_snapshot")
        if "revenue" in self.exec_kpi:
            if not _has_value(revenue):
                self.exec_kpi["revenue"][0].configure(text=UNAVAILABLE)
                self.exec_kpi["revenue"][1].configure(text="No revenue data")
            else:
                try:
                    amount = float(revenue)
                    self.exec_kpi["revenue"][0].configure(text=f"R{int(amount):,}")
                    self.exec_kpi["revenue"][1].configure(text="")
                except (TypeError, ValueError):
                    self.exec_kpi["revenue"][0].configure(text=str(revenue))
                    self.exec_kpi["revenue"][1].configure(text="")

        # ---- Departments / activity / approvals list ----
        if summary is None:
            departments = None
            activities = None
            approvals = None
        else:
            departments = (
                _v(summary, "departments")
                if _has_value(_v(summary, "departments"))
                else (
                    _v(summary, "department_performance")
                    if _has_value(_v(summary, "department_performance"))
                    else (
                        _v(summary, "dept_stats")
                        if _has_value(_v(summary, "dept_stats"))
                        else []
                    )
                )
            )
            activities = (
                _v(summary, "latest_activity")
                if _has_value(_v(summary, "latest_activity"))
                else (
                    _v(summary, "recent_activity")
                    if _has_value(_v(summary, "recent_activity"))
                    else (
                        _v(summary, "activity")
                        if _has_value(_v(summary, "activity"))
                        else []
                    )
                )
            )
            approvals = (
                _v(summary, "approvals_queue")
                if _has_value(_v(summary, "approvals_queue"))
                else (
                    _v(summary, "pending_approval_items")
                    if _has_value(_v(summary, "pending_approval_items"))
                    else (
                        _v(summary, "pending_approvals_list")
                        if _has_value(_v(summary, "pending_approvals_list"))
                        else []
                    )
                )
            )

        if hasattr(self, "dept_frame"):
            self._render_departments(departments)
        if hasattr(self, "exec_activity"):
            self._render_activity_rows(activities)
        if hasattr(self, "approvals_list"):
            self._render_approvals(approvals)

    def _apply_employee(self, summary) -> None:
        if not hasattr(self, "emp_kpi"):
            return
        tasks = _as_int_or_none(_v(summary, "tasks_due_today"))
        in_prog = _as_int_or_none(_v(summary, "tasks_in_progress"))
        if "tasks" in self.emp_kpi:
            self.emp_kpi["tasks"][0].configure(text=_fmt_int(tasks))
            self.emp_kpi["tasks"][1].configure(
                text="" if in_prog is None else f"{in_prog} in progress"
            )
        hours = _as_float_or_none(_v(summary, "hours_worked_today"))
        if "hours" in self.emp_kpi:
            if hours is None:
                self.emp_kpi["hours"][0].configure(text=UNAVAILABLE)
            else:
                self.emp_kpi["hours"][0].configure(
                    text=f"{int(hours)}h {int(round((hours % 1) * 60))}m"
                )
        leave = _v(summary, "leave_balance")
        if "leave" in self.emp_kpi:
            if not _has_value(leave):
                self.emp_kpi["leave"][0].configure(text=UNAVAILABLE)
            else:
                self.emp_kpi["leave"][0].configure(text=f"{leave} days")
        att = _v(summary, "attendance_status")
        if "attendance" in self.emp_kpi:
            self.emp_kpi["attendance"][0].configure(
                text=UNAVAILABLE if not _has_value(att) else str(att)
            )

    @staticmethod
    def _format_activity_time(value) -> str:
        if not value:
            return UNAVAILABLE
        try:
            if isinstance(value, datetime):
                dt = value
            else:
                text = str(value).strip()
                if text.endswith("Z"):
                    text = text[:-1] + "+00:00"
                dt = datetime.fromisoformat(text)
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            seconds = int((now - dt).total_seconds())
            if seconds < 60:
                return "Just now"
            minutes = seconds // 60
            if minutes < 60:
                return f"{minutes} min ago"
            hours = minutes // 60
            if hours < 24:
                return f"{hours}h ago"
            days = hours // 24
            if days == 1:
                return "Yesterday"
            if days < 7:
                return f"{days} days ago"
            return dt.strftime("%d %b %Y")
        except Exception:
            return str(value)[:16]

    def _scheduled_refresh(self) -> None:
        if self._is_destroyed:
            return
        self._safe_refresh()
        if self._is_destroyed:
            return
        try:
            if self.winfo_exists():
                self._refresh_job = self.after(
                    self.REFRESH_INTERVAL_MS, self._scheduled_refresh
                )
        except Exception:
            self._refresh_job = None

    def _refresh_data(self) -> None:
        self._safe_refresh()

    def destroy(self) -> None:
        if self._is_destroyed:
            return
        self._is_destroyed = True
        for job in (self._refresh_job, self._queue_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._refresh_job = self._queue_job = None
        try:
            super().destroy()
        except Exception:
            pass