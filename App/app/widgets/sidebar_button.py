"""Sidebar navigation button."""

from collections.abc import Callable

import customtkinter as ctk

from app.utils.theme import Theme


class SidebarButton(ctk.CTkFrame):
    """Reusable sidebar button with active and inactive states."""

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
        "User Management": "#9333EA",
        "Settings": "#64748B",
    }

    def __init__(self, master: object, text: str, command: Callable[[], None]) -> None:
        self._label = text
        super().__init__(
            master,
            height=40,
            corner_radius=Theme.RADIUS,
            fg_color="transparent",
        )
        self.grid_columnconfigure(1, weight=1)
        colour = self.ICON_COLOURS.get(text, Theme.ACCENT)
        self._icon = ctk.CTkLabel(
            self,
            text=self.ICONS.get(text, "•"),
            width=28,
            height=28,
            corner_radius=8,
            fg_color=colour,
            text_color="#FFFFFF",
            font=("Segoe UI Emoji", 12),
        )
        self._icon.grid(row=0, column=0, padx=(8, 8), pady=6)
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
        # Make the entire row clickable, including the icon and empty frame area.
        self._command = command
        self.bind("<Button-1>", lambda _event: self._command())
        self._icon.bind("<Button-1>", lambda _event: self._command())
        self.bind("<Enter>", lambda _event: self._button.configure(hover_color=Theme.PANEL_ALT))

    def set_active(self, is_active: bool) -> None:
        """Update visual state."""
        background = Theme.PANEL_ALT if is_active else "transparent"
        self.configure(fg_color=background)
        self._button.configure(
            fg_color=background,
            text_color=Theme.TEXT if is_active else Theme.MUTED_TEXT,
        )