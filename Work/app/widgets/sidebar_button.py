"""Sidebar navigation button."""

from collections.abc import Callable

import customtkinter as ctk

from app.utils.theme import Theme


class SidebarButton(ctk.CTkButton):
    """Reusable sidebar button with active and inactive states."""

    ICONS = {
        "Dashboard": "#",
        "Work": "W",
        "People": "P",
        "Attendance": "A",
        "Calendar": "C",
        "Approvals": "OK",
        "Office Requests": "+",
        "Notifications": "!",
        "Projects": "<>",
        "Tasks": "T",
        "Reports": "R",
        "Settings": "*",
    }

    def __init__(self, master: object, text: str, command: Callable[[], None]) -> None:
        self._label = text
        super().__init__(
            master,
            text=f"{self.ICONS.get(text, '-')}  {text}",
            command=command,
            height=40,
            corner_radius=Theme.RADIUS,
            anchor="w",
            font=Theme.FONT_BODY,
            fg_color="transparent",
            hover_color=Theme.PANEL_ALT,
            text_color=Theme.MUTED_TEXT,
            border_width=0,
        )

    def set_active(self, is_active: bool) -> None:
        """Update visual state."""
        self.configure(
            fg_color=Theme.PANEL_ALT if is_active else "transparent",
            text_color=Theme.TEXT if is_active else Theme.MUTED_TEXT,
        )
