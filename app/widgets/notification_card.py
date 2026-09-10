"""Reusable notification card."""

from collections.abc import Callable
from datetime import datetime

import customtkinter as ctk

from app.models.notification import Notification
from app.utils.theme import Theme


class NotificationCard(ctk.CTkFrame):
    """Displays a role-targeted notification and exposes a read command."""

    def __init__(
        self,
        master: object,
        notification: Notification,
        on_read: Callable[[object], None],
        accent_color: str | None = None,
        group_label: str = "General",
    ) -> None:
        self._accent_color = accent_color or Theme.ACCENT
        self._group_label = group_label
        super().__init__(
            master,
            fg_color=Theme.PANEL if notification.is_read else Theme.PANEL_ALT,
            border_color=Theme.BORDER if notification.is_read else self._accent_color,
            border_width=1 if notification.is_read else 2,
            corner_radius=Theme.RADIUS,
        )
        self._notification = notification
        self._on_read = on_read
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=168)
        ctk.CTkFrame(
            self,
            width=6,
            corner_radius=3,
            fg_color=self._accent_color,
        ).grid(row=0, column=0, rowspan=3, padx=(8, 0), pady=8, sticky="ns")

        ctk.CTkLabel(
            self, text=self._notification.title, text_color=Theme.TEXT,
            font=("Segoe UI", 15, "bold"), anchor="w"
        ).grid(row=0, column=1, padx=(14, 10), pady=(13, 3), sticky="ew")
        ctk.CTkLabel(
            self,
            text=self._group_label,
            text_color="#FFFFFF",
            fg_color=self._accent_color,
            corner_radius=10,
            padx=10,
            font=("Segoe UI", 11, "bold"),
            anchor="center",
        ).grid(row=0, column=2, padx=(8, 14), pady=(12, 3), sticky="e")
        ctk.CTkLabel(
            self, text=self._notification.message, text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12), justify="left", wraplength=600, anchor="w"
        ).grid(row=1, column=1, columnspan=2, padx=(14, 14), pady=(0, 8), sticky="ew")

        state_text = "Unread" if not self._notification.is_read else "Read"
        meta = self._notification.category or "General"
        created = self._format_created_at(self._notification.created_at)
        if created:
            meta = f"{meta}  ·  {created}"
        ctk.CTkLabel(
            self,
            text=f"{state_text}  ·  {meta}",
            text_color=self._accent_color if not self._notification.is_read else Theme.MUTED_TEXT,
            font=("Segoe UI", 11, "bold" if not self._notification.is_read else "normal"),
            anchor="w",
        ).grid(row=2, column=1, padx=(14, 10), pady=(0, 13), sticky="w")

        if not self._notification.is_read and self._notification.id is not None:
            ctk.CTkButton(
                self, text="✓  Mark as Read", height=36, width=150,
                fg_color=Theme.SUCCESS, hover_color=Theme.SUCCESS_HOVER,
                text_color="#FFFFFF", font=("Segoe UI", 12, "bold"),
                command=lambda: self._on_read(self._notification.id)
            ).grid(row=2, column=2, padx=(8, 14), pady=(0, 12), sticky="e")
        else:
            ctk.CTkButton(
                self,
                text="✓  Read",
                height=36,
                width=150,
                state="disabled",
                fg_color=Theme.INFO,
                text_color="#FFFFFF",
                text_color_disabled="#FFFFFF",
                font=("Segoe UI", 12, "bold"),
            ).grid(row=2, column=2, padx=(8, 14), pady=(0, 12), sticky="e")

    @staticmethod
    def _format_created_at(value: object) -> str:
        if not value:
            return ""
        if isinstance(value, datetime):
            parsed = value
        else:
            text = str(value).strip()
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return text[:16]
        return parsed.astimezone().strftime("%d %b %Y  %H:%M")
