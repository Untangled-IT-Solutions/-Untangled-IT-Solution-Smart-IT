"""Sidebar navigation button with optional unread badge."""

from collections.abc import Callable
from typing import Optional

import customtkinter as ctk

from app.utils.theme import Theme


class SidebarButton(ctk.CTkFrame):
    """Reusable sidebar button with active state and notification badge."""

    ICONS = {
        "Dashboard": "🏠",
        "Work": "💼",
        "People": "👥",
        "Attendance": "⏱️",
        "Calendar": "📅",
        "Approvals": "✅",
        "Office Requests": "🏢",
        "Notifications": "🔔",
        "Projects": "📁",
        "Tasks": "☑️",
        "Reports": "📊",
        "Quote Sync": "🔄",
        "Quote Management": "💬",
        "Order Management": "📦",
        "User Management": "👤",
        "Settings": "⚙️",
    }

    ICON_COLOURS = {
        "Dashboard": "#2563EB",
        "Work": "#A16207",
        "People": "#7C3AED",
        "Attendance": "#16A34A",
        "Calendar": "#DB2777",
        "Approvals": "#059669",
        "Office Requests": "#CA8A04",
        "Notifications": "#DC2626",
        "Projects": "#0F766E",
        "Tasks": "#EA580C",
        "Reports": "#4F46E5",
        "Quote Sync": "#0284C7",
        "Quote Management": "#A21CAF",
        "Order Management": "#0EA5E9",
        "User Management": "#9333EA",
        "Settings": "#64748B",
    }

    def __init__(self, master: object, text: str, command: Callable[[], None]) -> None:
        self._label = text
        self._badge_count = 0
        super().__init__(
            master,
            height=40,
            corner_radius=Theme.RADIUS,
            fg_color="transparent",
        )
        self.grid_columnconfigure(1, weight=1)
        colour = self.ICON_COLOURS.get(text, Theme.ACCENT)

        # Icon + badge container
        self._icon_wrap = ctk.CTkFrame(self, fg_color="transparent", width=36, height=36)
        self._icon_wrap.grid(row=0, column=0, padx=(8, 8), pady=6)
        self._icon_wrap.grid_propagate(False)

        self._icon = ctk.CTkLabel(
            self._icon_wrap,
            text=self.ICONS.get(text, "•"),
            width=28,
            height=28,
            corner_radius=8,
            fg_color=colour,
            text_color="#FFFFFF",
            font=("Segoe UI Emoji", 12),
        )
        self._icon.place(x=0, y=4)

        # WhatsApp-style red badge (hidden when 0)
        self._badge = ctk.CTkLabel(
            self._icon_wrap,
            text="",
            width=18,
            height=18,
            corner_radius=9,
            fg_color="#EF4444",
            text_color="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
        )
        # placed off until set_badge is called
        self._badge.place_forget()

        self._button = ctk.CTkButton(
            self,
            text=text,
            command=command,
            height=38,
            corner_radius=Theme.RADIUS,
            anchor="w",
            font=Theme.FONT_BODY,
            fg_color="transparent",
            hover_color=Theme.PANEL_ALT,
            text_color=Theme.MUTED_TEXT,
            border_width=0,
        )
        self._button.grid(row=0, column=1, padx=(0, 4), pady=1, sticky="ew")

        self._command = command
        self.bind("<Button-1>", lambda _event: self._command())
        self._icon.bind("<Button-1>", lambda _event: self._command())
        self._icon_wrap.bind("<Button-1>", lambda _event: self._command())
        self.bind("<Enter>", lambda _event: self._button.configure(hover_color=Theme.PANEL_ALT))

    def set_active(self, is_active: bool) -> None:
        """Update visual state."""
        background = Theme.PANEL_ALT if is_active else "transparent"
        self.configure(fg_color=background)
        self._button.configure(
            fg_color=background,
            text_color=Theme.TEXT if is_active else Theme.MUTED_TEXT,
        )

    def set_badge(self, count: int) -> None:
        """Show a WhatsApp-style unread count on the icon (0 hides it)."""
        try:
            count = int(count or 0)
        except (TypeError, ValueError):
            count = 0
        self._badge_count = max(0, count)
        if self._badge_count <= 0:
            self._badge.place_forget()
            return
        label = "9+" if self._badge_count > 9 else str(self._badge_count)
        self._badge.configure(text=label)
        # top-right of icon
        self._badge.place(x=16, y=0)

    @property
    def badge_count(self) -> int:
        return self._badge_count
