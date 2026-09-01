"""Reusable notification card."""

from collections.abc import Callable

import customtkinter as ctk

from app.models.notification import Notification
from app.utils.theme import Theme


class NotificationCard(ctk.CTkFrame):
    """Displays a role-targeted notification and exposes a read command."""

    def __init__(
        self,
        master: object,
        notification: Notification,
        on_read: Callable[[int], None],
    ) -> None:
        super().__init__(
            master,
            fg_color=Theme.PANEL if notification.is_read else Theme.PANEL_ALT,
            border_color=Theme.BORDER,
            border_width=1,
            corner_radius=Theme.RADIUS,
        )
        self._notification = notification
        self._on_read = on_read
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self, text=self._notification.title, text_color=Theme.TEXT,
            font=("Segoe UI", 15, "bold"), anchor="w"
        ).grid(row=0, column=0, padx=16, pady=(14, 3), sticky="ew")
        ctk.CTkLabel(
            self, text=self._notification.category, text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 11), anchor="e"
        ).grid(row=0, column=1, padx=16, pady=(14, 3), sticky="e")
        ctk.CTkLabel(
            self, text=self._notification.message, text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12), justify="left", wraplength=720, anchor="w"
        ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="ew")
        if not self._notification.is_read and self._notification.id is not None:
            ctk.CTkButton(
                self, text="Mark read", height=30, width=94,
                fg_color=Theme.PANEL, hover_color=Theme.BORDER,
                command=lambda: self._on_read(self._notification.id)
            ).grid(row=2, column=1, padx=16, pady=(0, 14), sticky="e")
