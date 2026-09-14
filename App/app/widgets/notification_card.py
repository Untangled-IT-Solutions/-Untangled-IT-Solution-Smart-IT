"""Reusable notification card with clear unread / missed styling."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Union

import customtkinter as ctk

from app.models.notification import Notification
from app.utils.theme import Theme


def _format_when(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        cleaned = text.replace("Z", "+00:00")
        if "T" in cleaned:
            dt = datetime.fromisoformat(cleaned)
        else:
            return text[:16]
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return text[:19].replace("T", " ")


class NotificationCard(ctk.CTkFrame):
    """Displays a notification. Unread items show a red dot + Mark read button."""

    UNREAD_ACCENT = "#DC2626"
    UNREAD_BG_LIGHT = "#FEF2F2"
    UNREAD_BG_DARK = "#2A1515"

    def __init__(
        self,
        master: object,
        notification: Notification,
        on_read: Callable[[Union[str, int]], None],
    ) -> None:
        unread = not bool(notification.is_read)
        try:
            dark = str(getattr(Theme, "CURRENT_MODE", "light")).lower() == "dark"
        except Exception:
            dark = False
        if unread:
            bg = self.UNREAD_BG_DARK if dark else self.UNREAD_BG_LIGHT
            border = self.UNREAD_ACCENT
        else:
            bg = Theme.PANEL
            border = Theme.BORDER

        super().__init__(
            master,
            fg_color=bg,
            border_color=border,
            border_width=2 if unread else 1,
            corner_radius=Theme.RADIUS,
        )
        self._notification = notification
        self._on_read = on_read
        self._unread = unread
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        # Left accent / unread dot column
        left = ctk.CTkFrame(self, fg_color="transparent", width=28)
        left.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(10, 0), pady=10)
        left.grid_propagate(False)
        if self._unread:
            ctk.CTkLabel(
                left,
                text="●",
                text_color=self.UNREAD_ACCENT,
                font=("Segoe UI", 14),
            ).pack(pady=(6, 0))
        else:
            ctk.CTkLabel(
                left,
                text="○",
                text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 12),
            ).pack(pady=(6, 0))

        when = _format_when(self._notification.created_at)
        meta = self._notification.category or "General"
        if when:
            meta = f"{meta}  ·  {when}"

        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.grid(row=0, column=1, sticky="ew", padx=(4, 8), pady=(12, 2))
        title_row.grid_columnconfigure(0, weight=1)

        title_text = self._notification.title or "Notification"
        if self._unread:
            title_text = f"{title_text}"

        ctk.CTkLabel(
            title_row,
            text=title_text,
            text_color=Theme.TEXT,
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        if self._unread:
            ctk.CTkLabel(
                title_row,
                text="MISSED",
                text_color="#FFFFFF",
                fg_color=self.UNREAD_ACCENT,
                corner_radius=6,
                font=("Segoe UI", 10, "bold"),
                width=58,
                height=20,
            ).grid(row=0, column=1, padx=(8, 0), sticky="e")

        ctk.CTkLabel(
            self,
            text=meta,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 11),
            anchor="e",
        ).grid(row=0, column=2, padx=16, pady=(12, 2), sticky="e")

        ctk.CTkLabel(
            self,
            text=self._notification.message or "",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12),
            justify="left",
            wraplength=680,
            anchor="w",
        ).grid(row=1, column=1, columnspan=2, padx=(4, 16), pady=(0, 8), sticky="ew")

        # Always show Mark read for unread items when we have an id
        if self._unread:
            btn_row = ctk.CTkFrame(self, fg_color="transparent")
            btn_row.grid(row=2, column=1, columnspan=2, sticky="e", padx=16, pady=(0, 12))
            nid = self._notification.id
            if nid is not None and str(nid).strip():
                ctk.CTkButton(
                    btn_row,
                    text="Mark as read",
                    height=30,
                    width=120,
                    fg_color=Theme.ACCENT if hasattr(Theme, "ACCENT") else "#60920D",
                    hover_color=Theme.ACCENT_HOVER if hasattr(Theme, "ACCENT_HOVER") else "#4d760a",
                    text_color="#FFFFFF",
                    command=lambda i=nid: self._on_read(i),
                ).pack(side="right")
            else:
                ctk.CTkLabel(
                    btn_row,
                    text="No id – cannot mark",
                    text_color=self.UNREAD_ACCENT,
                    font=("Segoe UI", 11),
                ).pack(side="right")
