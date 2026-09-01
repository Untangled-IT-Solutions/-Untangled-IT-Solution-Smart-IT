# app/views/dashboard_view.py
"""
Untangled Nexus - Professional Desktop Dashboard

Responsibilities:
    - Display the logged-in user's dashboard
    - Display real dashboard information from DashboardController
    - Provide simple Quick Actions
    - Display recent operational activity
    - Use the application's existing NavigationController
    - No direct database access
    - No fake/demo dashboard data

Designed for desktop resolutions including:
    - 1366 x 768
    - 1366 x 900
    - 1440 x 900
    - 1920 x 1080
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import queue
import threading

import customtkinter as ctk

from app.controllers.dashboard_controller import DashboardController
from app.utils.theme import Theme


class DashboardView(ctk.CTkFrame):
    """Professional desktop dashboard for Untangled Nexus."""

    REFRESH_INTERVAL_MS = 30_000

    # Dashboard sizing
    OUTER_PAD_X = 28
    SECTION_GAP = 16

    def __init__(
        self,
        master,
        controller: DashboardController,
    ) -> None:
        super().__init__(
            master,
            fg_color=Theme.BG,
            corner_radius=0,
        )

        self._controller = controller
        self._refresh_job: Optional[str] = None
        self._queue_job: Optional[str] = None
        self._is_destroyed = False
        self._refresh_running = False
        self._backend_queue: queue.Queue = queue.Queue()

        self._account = self._find_current_account()
        self._navigation_controller = self._find_navigation_controller()

        self._build_layout()

        # Drain worker results on Tk's main thread. Network I/O never runs
        # inside a Tk callback.
        self._queue_job = self.after(50, self._drain_backend_queue)

        # Load real data after the view is displayed.
        self.after(150, self._safe_refresh)

        # Continue refreshing dashboard information.
        self._refresh_job = self.after(
            self.REFRESH_INTERVAL_MS,
            self._scheduled_refresh,
        )

    # ==================================================================
    # ACCOUNT / MAIN WINDOW DISCOVERY
    # ==================================================================

    def _find_main_window(self):
        """Walk up the widget hierarchy until MainWindow is found."""

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
        """Return the authenticated account from MainWindow."""

        main_window = self._find_main_window()

        if main_window is None:
            return None

        try:
            return getattr(
                main_window,
                "_current_account",
                None,
            )
        except Exception:
            return None

    def _find_navigation_controller(self):
        """Return the existing NavigationController."""

        main_window = self._find_main_window()

        if main_window is None:
            return None

        try:
            return getattr(
                main_window,
                "_navigation_controller",
                None,
            )
        except Exception:
            return None

    # ==================================================================
    # GENERAL HELPERS
    # ==================================================================

    @staticmethod
    def _value(
        source: Any,
        name: str,
        default: Any = 0,
    ) -> Any:
        """
        Safely read either an object attribute or dictionary value.

        This keeps the dashboard compatible with the existing
        DashboardSummary implementation.
        """

        if source is None:
            return default

        if isinstance(source, dict):
            return source.get(name, default)

        try:
            return getattr(
                source,
                name,
                default,
            )
        except Exception:
            return default

    # ==================================================================
    # MAIN LAYOUT
    # ==================================================================

    def _build_layout(self) -> None:
        """Build the complete desktop dashboard."""

        self.grid_columnconfigure(
            0,
            weight=1,
        )

        self.grid_rowconfigure(
            0,
            weight=1,
        )

        # --------------------------------------------------------------
        # Scrollable workspace
        # --------------------------------------------------------------

        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=Theme.PANEL_ALT,
            scrollbar_button_hover_color=Theme.BORDER,
        )

        self.content.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.content.grid_columnconfigure(
            0,
            weight=1,
        )

        self._build_page_heading()
        self._build_welcome_card()
        self._build_kpis()
        self._build_work_area()
        self._build_recent_activity()

    # ==================================================================
    # PAGE HEADING
    # ==================================================================

    def _build_page_heading(self) -> None:
        """Dashboard title and refresh controls."""

        self.heading = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        self.heading.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=self.OUTER_PAD_X,
            pady=(22, 10),
        )

        self.heading.grid_columnconfigure(
            0,
            weight=1,
        )

        # Left
        title_frame = ctk.CTkFrame(
            self.heading,
            fg_color="transparent",
        )

        title_frame.grid(
            row=0,
            column=0,
            sticky="w",
        )

        ctk.CTkLabel(
            title_frame,
            text="Dashboard",
            text_color=Theme.TEXT,
            font=("Segoe UI", 26, "bold"),
            anchor="w",
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            title_frame,
            text="Your operational overview at a glance",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 11),
            anchor="w",
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

        # Right
        control_frame = ctk.CTkFrame(
            self.heading,
            fg_color="transparent",
        )

        control_frame.grid(
            row=0,
            column=1,
            sticky="e",
        )

        self.updated_label = ctk.CTkLabel(
            control_frame,
            text="",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 9),
        )

        self.updated_label.grid(
            row=0,
            column=0,
            padx=(0, 12),
        )

        ctk.CTkButton(
            control_frame,
            text="Refresh",
            width=82,
            height=34,
            corner_radius=7,
            fg_color=Theme.PANEL,
            hover_color=Theme.PANEL_ALT,
            border_width=1,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
            font=("Segoe UI", 10, "bold"),
            command=self._safe_refresh,
        ).grid(
            row=0,
            column=1,
        )

    # ==================================================================
    # WELCOME CARD
    # ==================================================================

    def _build_welcome_card(self) -> None:
        """Build the logged-in user welcome panel."""

        self.welcome_card = ctk.CTkFrame(
            self.content,
            fg_color=Theme.PANEL,
            corner_radius=12,
            border_width=1,
            border_color=Theme.BORDER,
        )

        self.welcome_card.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=self.OUTER_PAD_X,
            pady=(0, self.SECTION_GAP),
        )

        self.welcome_card.grid_columnconfigure(
            0,
            weight=1,
        )

        self.welcome_card.grid_columnconfigure(
            1,
            weight=0,
        )

        # --------------------------------------------------------------
        # Left side
        # --------------------------------------------------------------

        left = ctk.CTkFrame(
            self.welcome_card,
            fg_color="transparent",
        )

        left.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(24, 20),
            pady=20,
        )

        self.greeting_label = ctk.CTkLabel(
            left,
            text="Good evening",
            text_color=Theme.TEXT,
            font=("Segoe UI", 24, "bold"),
            anchor="w",
        )

        self.greeting_label.pack(
            anchor="w",
        )

        self.welcome_subtitle = ctk.CTkLabel(
            left,
            text="Welcome back. Here's your operational overview for today.",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 11),
            anchor="w",
        )

        self.welcome_subtitle.pack(
            anchor="w",
            pady=(5, 12),
        )

        self.role_badge = ctk.CTkLabel(
            left,
            text="Signed in as User",
            text_color=Theme.TEXT,
            fg_color=Theme.PANEL_ALT,
            corner_radius=7,
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=6,
        )

        self.role_badge.pack(
            anchor="w",
        )

        # --------------------------------------------------------------
        # Right side
        # --------------------------------------------------------------

        date_frame = ctk.CTkFrame(
            self.welcome_card,
            fg_color="transparent",
        )

        date_frame.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(20, 24),
            pady=20,
        )

        self.day_label = ctk.CTkLabel(
            date_frame,
            text="",
            text_color=Theme.TEXT,
            font=("Segoe UI", 12, "bold"),
            anchor="e",
        )

        self.day_label.pack(
            anchor="e",
        )

        self.date_label = ctk.CTkLabel(
            date_frame,
            text="",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 10),
            anchor="e",
        )

        self.date_label.pack(
            anchor="e",
            pady=(4, 0),
        )

        self._update_welcome_information()

    # ==================================================================
    # KPI SECTION
    # ==================================================================

    def _build_kpis(self) -> None:
        """Build the five main dashboard KPI cards."""

        self.kpi_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        self.kpi_frame.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=self.OUTER_PAD_X,
            pady=(0, self.SECTION_GAP),
        )

        for column in range(5):
            self.kpi_frame.grid_columnconfigure(
                column,
                weight=1,
                uniform="dashboard_kpi",
            )

        definitions = [
            (
                "People Working",
                "Currently active",
                Theme.SUCCESS,
            ),
            (
                "Tasks Due Today",
                "Due today",
                Theme.WARNING,
            ),
            (
                "Tasks Overdue",
                "Needs attention",
                Theme.DANGER,
            ),
            (
                "Pending Approvals",
                "Awaiting action",
                Theme.ACCENT,
            ),
            (
                "Active Work",
                "Open work items",
                Theme.SUCCESS,
            ),
        ]

        self.kpi_cards = []

        for index, (
            title,
            subtitle,
            accent,
        ) in enumerate(definitions):

            card = self._create_kpi_card(
                self.kpi_frame,
                title,
                subtitle,
                accent,
            )

            card.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=(0 if index == 0 else 5, 0 if index == 4 else 5),
            )

            self.kpi_cards.append(card)

    def _create_kpi_card(
        self,
        parent,
        title: str,
        subtitle: str,
        accent: str,
    ):
        """
        Create a KPI card.

        Important:
            This intentionally does NOT use grid_propagate(False).
            The previous implementation clipped the values because
            the card height was smaller than its internal content.
        """

        card = ctk.CTkFrame(
            parent,
            fg_color=Theme.PANEL,
            corner_radius=10,
            border_width=1,
            border_color=Theme.BORDER,
            height=126,
        )

        card.grid_propagate(False)

        # Two columns:
        #   0 = accent strip
        #   1 = content
        card.grid_columnconfigure(
            1,
            weight=1,
        )

        card.grid_rowconfigure(
            0,
            weight=0,
        )

        card.grid_rowconfigure(
            1,
            weight=1,
        )

        card.grid_rowconfigure(
            2,
            weight=0,
        )

        accent_strip = ctk.CTkFrame(
            card,
            width=4,
            fg_color=accent,
            corner_radius=2,
        )

        accent_strip.grid(
            row=0,
            column=0,
            rowspan=3,
            sticky="ns",
            padx=(0, 12),
            pady=12,
        )

        title_label = ctk.CTkLabel(
            card,
            text=title,
            text_color=Theme.TEXT,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )

        title_label.grid(
            row=0,
            column=1,
            padx=(0, 12),
            pady=(15, 0),
            sticky="w",
        )

        value_label = ctk.CTkLabel(
            card,
            text="0",
            text_color=Theme.TEXT,
            font=("Segoe UI", 25, "bold"),
            anchor="w",
        )

        value_label.grid(
            row=1,
            column=1,
            padx=(0, 12),
            pady=(2, 0),
            sticky="w",
        )

        subtitle_label = ctk.CTkLabel(
            card,
            text=subtitle,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 9),
            anchor="w",
        )

        subtitle_label.grid(
            row=2,
            column=1,
            padx=(0, 12),
            pady=(0, 13),
            sticky="w",
        )

        # Store the label safely.
        card._value_label = value_label

        return card

    # ==================================================================
    # WORK AREA
    # ==================================================================

    def _build_work_area(self) -> None:
        """
        Build:
            left  = Work Overview
            right = Quick Actions
        """

        self.work_row = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        self.work_row.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=self.OUTER_PAD_X,
            pady=(0, self.SECTION_GAP),
        )

        self.work_row.grid_columnconfigure(
            0,
            weight=7,
            uniform="work_area",
        )

        self.work_row.grid_columnconfigure(
            1,
            weight=4,
            uniform="work_area",
        )

        self._build_work_overview()
        self._build_quick_actions()

    # ==================================================================
    # WORK OVERVIEW
    # ==================================================================

    def _build_work_overview(self) -> None:
        """Build the operational work overview."""

        self.operations_card = ctk.CTkFrame(
            self.work_row,
            fg_color=Theme.PANEL,
            corner_radius=12,
            border_width=1,
            border_color=Theme.BORDER,
            height=236,
        )

        self.operations_card.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 7),
        )

        self.operations_card.grid_propagate(False)

        self.operations_card.grid_columnconfigure(
            0,
            weight=1,
            uniform="overview",
        )

        self.operations_card.grid_columnconfigure(
            1,
            weight=1,
            uniform="overview",
        )

        self.operations_card.grid_columnconfigure(
            2,
            weight=1,
            uniform="overview",
        )

        # Header
        ctk.CTkLabel(
            self.operations_card,
            text="Work Overview",
            text_color=Theme.TEXT,
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            padx=18,
            pady=(17, 2),
        )

        ctk.CTkLabel(
            self.operations_card,
            text="A quick look at your current workload and operational status.",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 10),
            anchor="w",
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="w",
            padx=18,
            pady=(0, 14),
        )

        self.overview_cards = []

        definitions = [
            (
                "Ops Inbox",
                Theme.SUCCESS,
                "Dumped tasks waiting for triage",
            ),
            (
                "Waiting Review",
                Theme.WARNING,
                "Items waiting for review",
            ),
            (
                "Upcoming Deadlines",
                Theme.ACCENT,
                "Items needing attention soon",
            ),
        ]

        for index, (
            title,
            accent,
            description,
        ) in enumerate(definitions):

            box = ctk.CTkFrame(
                self.operations_card,
                fg_color=Theme.PANEL_ALT,
                corner_radius=9,
                border_width=1,
                border_color=Theme.BORDER,
                height=112,
            )

            box.grid(
                row=2,
                column=index,
                sticky="nsew",
                padx=(6 if index > 0 else 14, 6 if index < 2 else 14),
                pady=(0, 17),
            )

            box.grid_propagate(False)

            box.grid_rowconfigure(
                0,
                weight=0,
            )

            box.grid_rowconfigure(
                1,
                weight=0,
            )

            box.grid_rowconfigure(
                2,
                weight=1,
            )

            value_label = ctk.CTkLabel(
                box,
                text="0",
                text_color=accent,
                font=("Segoe UI", 23, "bold"),
            )

            value_label.grid(
                row=0,
                column=0,
                pady=(13, 0),
            )

            label = ctk.CTkLabel(
                box,
                text=title,
                text_color=Theme.TEXT,
                font=("Segoe UI", 10, "bold"),
            )

            label.grid(
                row=1,
                column=0,
                pady=(2, 0),
            )

            description_label = ctk.CTkLabel(
                box,
                text=description,
                text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 8),
                wraplength=160,
                justify="center",
            )

            description_label.grid(
                row=2,
                column=0,
                padx=8,
                pady=(3, 8),
            )

            box._value_label = value_label

            self.overview_cards.append(box)

    # ==================================================================
    # QUICK ACTIONS
    # ==================================================================

    def _build_quick_actions(self) -> None:
        """Build simple, obvious navigation actions."""

        self.quick_card = ctk.CTkFrame(
            self.work_row,
            fg_color=Theme.PANEL,
            corner_radius=12,
            border_width=1,
            border_color=Theme.BORDER,
            height=236,
        )

        self.quick_card.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(7, 0),
        )

        self.quick_card.grid_propagate(False)

        self.quick_card.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkLabel(
            self.quick_card,
            text="Quick Actions",
            text_color=Theme.TEXT,
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=18,
            pady=(17, 2),
        )

        ctk.CTkLabel(
            self.quick_card,
            text="Go directly to the areas you use most.",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 10),
            anchor="w",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=18,
            pady=(0, 10),
        )

        self._create_quick_action(
            row=2,
            title="My Work",
            description="Assigned quotes and work",
            destination="Work",
        )

        self._create_quick_action(
            row=3,
            title="Attendance",
            description="Clock in and manage breaks",
            destination="Attendance",
        )

        self._create_quick_action(
            row=4,
            title="Tasks",
            description="View your assigned tasks",
            destination="Tasks",
        )

    def _create_quick_action(
        self,
        row: int,
        title: str,
        description: str,
        destination: str,
    ) -> None:
        """Create one clean quick-action row."""

        action = ctk.CTkFrame(
            self.quick_card,
            fg_color=Theme.PANEL_ALT,
            corner_radius=8,
            border_width=1,
            border_color=Theme.BORDER,
            height=50,
        )

        action.grid(
            row=row,
            column=0,
            sticky="ew",
            padx=14,
            pady=4,
        )

        action.grid_propagate(False)

        action.grid_columnconfigure(
            0,
            weight=1,
        )

        # Text
        text_frame = ctk.CTkFrame(
            action,
            fg_color="transparent",
        )

        text_frame.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(12, 4),
        )

        ctk.CTkLabel(
            text_frame,
            text=title,
            text_color=Theme.TEXT,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            text_frame,
            text=description,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(
            anchor="w",
            pady=(1, 0),
        )

        # Button
        ctk.CTkButton(
            action,
            text="Open",
            width=58,
            height=29,
            corner_radius=6,
            fg_color=Theme.BG,
            hover_color=Theme.BORDER,
            border_width=1,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
            font=("Segoe UI", 9, "bold"),
            command=lambda d=destination: self._navigate(d),
        ).grid(
            row=0,
            column=1,
            padx=(4, 10),
        )

    # ==================================================================
    # RECENT ACTIVITY
    # ==================================================================

    def _build_recent_activity(self) -> None:
        """Build the recent activity feed."""

        self.activity_card = ctk.CTkFrame(
            self.content,
            fg_color=Theme.PANEL,
            corner_radius=12,
            border_width=1,
            border_color=Theme.BORDER,
        )

        self.activity_card.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=self.OUTER_PAD_X,
            pady=(0, 26),
        )

        self.activity_card.grid_columnconfigure(
            0,
            weight=1,
        )

        # Header
        header = ctk.CTkFrame(
            self.activity_card,
            fg_color="transparent",
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=18,
            pady=(16, 10),
        )

        header.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkLabel(
            header,
            text="Recent Activity",
            text_color=Theme.TEXT,
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )

        ctk.CTkLabel(
            header,
            text="The latest operational events from your workspace.",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 10),
            anchor="w",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(2, 0),
        )

        # Activity list
        self.activity_list = ctk.CTkScrollableFrame(
            self.activity_card,
            height=185,
            fg_color=Theme.PANEL_ALT,
            corner_radius=8,
            scrollbar_button_color=Theme.BORDER,
            scrollbar_button_hover_color=Theme.MUTED_TEXT,
        )

        self.activity_list.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=14,
            pady=(0, 14),
        )

        self.activity_list.grid_columnconfigure(
            0,
            weight=1,
        )

    # ==================================================================
    # WELCOME INFORMATION
    # ==================================================================

    def _update_welcome_information(self) -> None:
        """Update greeting, logged-in user, role and date."""

        now = datetime.now()

        if now.hour < 12:
            greeting = "Good morning"
        elif now.hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        name = "there"
        role = "User"

        account = self._account

        if account is not None:
            try:
                account_name = self._value(
                    account,
                    "full_name",
                    None,
                )

                if account_name:
                    name = str(
                        account_name
                    ).strip()

                account_role = self._value(
                    account,
                    "role",
                    None,
                )

                if account_role:
                    role = self._format_role(
                        str(account_role)
                    )

            except Exception:
                pass

        self.greeting_label.configure(
            text=f"{greeting}, {name}"
        )

        self.role_badge.configure(
            text=f"Signed in as {role}"
        )

        self.day_label.configure(
            text=now.strftime("%A")
        )

        self.date_label.configure(
            text=now.strftime("%d %B %Y")
        )

    @staticmethod
    def _format_role(role: str) -> str:
        """Convert stored role names into readable labels."""

        cleaned = (
            role
            .replace("_", " ")
            .replace("-", " ")
            .strip()
        )

        replacements = {
            "admin": "Administrator",
            "administrator": "Administrator",
            "director": "Director",
            "manager": "Manager",
            "business lead": "Business Lead",
            "employee": "Employee",
            "staff": "Employee",
            "user": "User",
        }

        lowered = cleaned.lower()

        if lowered in replacements:
            return replacements[lowered]

        return cleaned.title()

    # ==================================================================
    # NAVIGATION
    # ==================================================================

    def _navigate(self, destination: str) -> None:
        """Navigate through the existing application navigation."""

        if self._navigation_controller is None:
            print(
                "⚠️ Dashboard navigation unavailable: "
                f"{destination}"
            )
            return

        try:
            self._navigation_controller.navigate(
                destination
            )

        except Exception as exc:
            print(
                "⚠️ Dashboard navigation error "
                f"for {destination}: {exc}"
            )

    # ==================================================================
    # DATA REFRESH
    # ==================================================================

    def _safe_refresh(self) -> None:
        """Schedule a dashboard refresh without blocking Tkinter."""

        if self._is_destroyed or self._refresh_running:
            return

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self._refresh_running = True

        def worker() -> None:
            try:
                summary = self._controller.get_summary()
                self._backend_queue.put((True, summary, None))
            except Exception as exc:
                self._backend_queue.put((False, None, exc))

        threading.Thread(
            target=worker,
            daemon=True,
            name="DashboardAPI",
        ).start()

    def _drain_backend_queue(self) -> None:
        """Apply completed backend requests safely on Tk's main thread."""
        if self._is_destroyed:
            return

        try:
            while True:
                success, summary, error = self._backend_queue.get_nowait()
                self._refresh_running = False

                if success:
                    self._apply_summary(summary)
                else:
                    print(f"⚠️ Dashboard refresh error: {error}")
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
        """Render an already-fetched summary on the Tk main thread."""
        if self._is_destroyed:
            return

        try:
            self._update_kpis(summary)
            self._update_operations(summary)

            activities = self._value(summary, "latest_activity", ())
            self._update_activity(activities)
            self._update_welcome_information()

            if hasattr(self, "updated_label"):
                self.updated_label.configure(
                    text="Updated " + datetime.now().strftime("%H:%M")
                )
        except Exception as exc:
            print(f"⚠️ Dashboard render error: {exc}")

    def _scheduled_refresh(self) -> None:
        """Run the next automatic dashboard refresh."""

        if self._is_destroyed:
            return

        self._safe_refresh()

        if self._is_destroyed:
            return

        try:
            if self.winfo_exists():
                self._refresh_job = self.after(
                    self.REFRESH_INTERVAL_MS,
                    self._scheduled_refresh,
                )
        except Exception:
            self._refresh_job = None

    def _refresh_data(self) -> None:
        """Compatibility alias for callers that request a refresh."""
        self._safe_refresh()

    # ==================================================================
    # KPI DATA
    # ==================================================================

    def _update_kpis(
        self,
        summary,
    ) -> None:
        """Update the five KPI values."""

        values = [
            self._value(
                summary,
                "people_working",
                0,
            ),
            self._value(
                summary,
                "tasks_due_today",
                0,
            ),
            self._value(
                summary,
                "tasks_overdue",
                0,
            ),
            self._value(
                summary,
                "pending_approvals",
                0,
            ),
            self._calculate_active_work(
                summary
            ),
        ]

        for card, value in zip(
            self.kpi_cards,
            values,
        ):
            try:
                card._value_label.configure(
                    text=str(
                        value if value is not None else 0
                    )
                )
            except Exception:
                pass

    def _calculate_active_work(
        self,
        summary,
    ) -> int:
        """
        Calculate active work from real summary values.

        Active Work =
            tasks currently in progress
            +
            pending tasks
        """

        in_progress = self._value(
            summary,
            "tasks_in_progress",
            0,
        )

        pending = self._value(
            summary,
            "pending_tasks",
            0,
        )

        try:
            return (
                int(in_progress or 0)
                + int(pending or 0)
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0

    # ==================================================================
    # OPERATIONS DATA
    # ==================================================================

    def _update_operations(
        self,
        summary,
    ) -> None:
        """Update Work Overview cards."""

        values = [
            self._value(
                summary,
                "operations_inbox",
                0,
            ),
            self._value(
                summary,
                "tasks_waiting_review",
                0,
            ),
            self._value(
                summary,
                "upcoming_deadlines",
                0,
            ),
        ]

        for card, value in zip(
            self.overview_cards,
            values,
        ):
            try:
                card._value_label.configure(
                    text=str(
                        value if value is not None else 0
                    )
                )
            except Exception:
                pass

    # ==================================================================
    # ACTIVITY
    # ==================================================================

    def _update_activity(
        self,
        activities,
    ) -> None:
        """Render recent activity as readable event cards."""

        if self._is_destroyed:
            return

        try:
            if not self.activity_list.winfo_exists():
                return
        except Exception:
            return

        # Clear previous activity
        for widget in self.activity_list.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

        if not activities:
            self._show_empty_activity()
            return

        try:
            activities = list(
                activities
            )
        except Exception:
            activities = []

        for activity in activities:
            self._create_activity_item(
                activity
            )

    def _show_empty_activity(self) -> None:
        """Display a friendly empty-state message."""

        empty = ctk.CTkFrame(
            self.activity_list,
            fg_color=Theme.PANEL,
            corner_radius=8,
            border_width=1,
            border_color=Theme.BORDER,
            height=75,
        )

        empty.pack(
            fill="x",
            padx=7,
            pady=7,
        )

        empty.pack_propagate(False)

        ctk.CTkLabel(
            empty,
            text="No recent activity",
            text_color=Theme.TEXT,
            font=("Segoe UI", 11, "bold"),
        ).pack(
            pady=(15, 0)
        )

        ctk.CTkLabel(
            empty,
            text="New operational events will appear here.",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 9),
        ).pack(
            pady=(2, 0)
        )

    def _create_activity_item(
        self,
        activity,
    ) -> None:
        """Create one clean activity event."""

        category = self._value(
            activity,
            "category",
            "Activity",
        ) or "Activity"

        description = self._value(
            activity,
            "description",
            "",
        ) or ""

        created_at = self._value(
            activity,
            "created_at",
            None,
        )

        category_display = (
            str(category)
            .replace("_", " ")
            .replace("-", " ")
            .title()
        )

        timestamp = self._format_activity_time(
            created_at
        )

        item = ctk.CTkFrame(
            self.activity_list,
            fg_color=Theme.PANEL,
            corner_radius=8,
            border_width=1,
            border_color=Theme.BORDER,
            height=62,
        )

        item.pack(
            fill="x",
            padx=7,
            pady=4,
        )

        item.pack_propagate(False)

        item.grid_columnconfigure(
            1,
            weight=1,
        )

        # --------------------------------------------------------------
        # Accent
        # --------------------------------------------------------------

        indicator = ctk.CTkFrame(
            item,
            width=4,
            fg_color=self._activity_color(
                category
            ),
            corner_radius=2,
        )

        indicator.grid(
            row=0,
            column=0,
            rowspan=2,
            sticky="ns",
            padx=(10, 10),
            pady=10,
        )

        # --------------------------------------------------------------
        # Category
        # --------------------------------------------------------------

        ctk.CTkLabel(
            item,
            text=category_display,
            text_color=Theme.TEXT,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 10),
            pady=(9, 0),
        )

        # --------------------------------------------------------------
        # Description
        # --------------------------------------------------------------

        ctk.CTkLabel(
            item,
            text=str(description),
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 9),
            anchor="w",
        ).grid(
            row=1,
            column=1,
            sticky="w",
            padx=(0, 10),
            pady=(0, 8),
        )

        # --------------------------------------------------------------
        # Time
        # --------------------------------------------------------------

        ctk.CTkLabel(
            item,
            text=timestamp,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 9),
            anchor="e",
        ).grid(
            row=0,
            column=2,
            rowspan=2,
            sticky="e",
            padx=(10, 14),
        )

    @staticmethod
    def _activity_color(
        category: str,
    ) -> str:
        """Return an appropriate activity accent."""

        category = str(
            category or ""
        ).lower()

        if "attendance" in category:
            return Theme.SUCCESS

        if "task" in category:
            return Theme.WARNING

        if "work" in category:
            return Theme.ACCENT

        if "approval" in category:
            return Theme.DANGER

        if "quote" in category:
            return Theme.ACCENT

        if "notification" in category:
            return Theme.WARNING

        return Theme.SUCCESS

    @staticmethod
    def _format_activity_time(
        value,
    ) -> str:
        """Convert activity timestamp into friendly text."""

        if not value:
            return "Recently"

        try:
            if isinstance(
                value,
                datetime,
            ):
                dt = value

            else:
                text = str(
                    value
                ).strip()

                if text.endswith("Z"):
                    text = (
                        text[:-1]
                        + "+00:00"
                    )

                dt = datetime.fromisoformat(
                    text
                )

            if dt.tzinfo:
                now = datetime.now(
                    dt.tzinfo
                )
            else:
                now = datetime.now()

            delta = (
                now - dt
            )

            seconds = int(
                delta.total_seconds()
            )

            if seconds < 0:
                return dt.strftime(
                    "%d %b %Y, %H:%M"
                )

            if seconds < 60:
                return "Just now"

            minutes = seconds // 60

            if minutes < 60:
                unit = (
                    "minute"
                    if minutes == 1
                    else "minutes"
                )

                return (
                    f"{minutes} "
                    f"{unit} ago"
                )

            hours = minutes // 60

            if hours < 24:
                unit = (
                    "hour"
                    if hours == 1
                    else "hours"
                )

                return (
                    f"{hours} "
                    f"{unit} ago"
                )

            days = hours // 24

            if days == 1:
                return "Yesterday"

            if days < 7:
                return (
                    f"{days} days ago"
                )

            return dt.strftime(
                "%d %b %Y, %H:%M"
            )

        except Exception:
            text = str(
                value
            )

            if len(text) >= 16:
                return text[:16].replace(
                    "T",
                    " ",
                )

            return text

    # ==================================================================
    # DESTROY
    # ==================================================================

    def destroy(self) -> None:
        """Cleanly destroy the dashboard."""

        if self._is_destroyed:
            return

        self._is_destroyed = True

        if self._refresh_job:
            try:
                self.after_cancel(
                    self._refresh_job
                )
            except Exception:
                pass

            self._refresh_job = None

        if self._queue_job:
            try:
                self.after_cancel(self._queue_job)
            except Exception:
                pass
            self._queue_job = None

        try:
            super().destroy()
        except Exception:
            pass
