"""Dashboard summary card widget."""

from collections.abc import Callable

import customtkinter as ctk

from app.utils.theme import Theme


class SummaryCard(ctk.CTkFrame):
    """Reusable card for displaying a single dashboard metric."""

    def __init__(
        self,
        master: object,
        title: str,
        value: str,
        accent_color: str,
        icon: str = "▦",
        command: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            master,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=0,
            corner_radius=Theme.RADIUS,
        )
        self._accent_color = accent_color
        self._command = command
        self.configure(height=148, cursor="hand2" if command else "")
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            self,
            text=icon,
            width=34,
            height=34,
            fg_color=Theme.PANEL_ALT,
            corner_radius=Theme.RADIUS,
            text_color=accent_color,
            font=(Theme.FONT_FAMILY, 16, "bold"),
        ).grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        ctk.CTkLabel(
            self,
            text="Open",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=0, column=1, padx=20, pady=(18, 4), sticky="e")

        ctk.CTkLabel(
            self,
            text=title,
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=1, column=0, columnspan=2, padx=20, pady=(8, 2), sticky="w")

        ctk.CTkLabel(
            self,
            text=value,
            text_color=Theme.TEXT,
            font=(Theme.FONT_FAMILY, 34, "bold"),
        ).grid(row=2, column=0, columnspan=2, padx=20, sticky="w")

        ctk.CTkFrame(self, height=3, fg_color=accent_color, corner_radius=2).grid(
            row=3,
            column=0,
            columnspan=2,
            padx=20,
            pady=(14, 0),
            sticky="ew",
        )
        if command is not None:
            self._bind_click_handler(self)

    def _bind_click_handler(self, widget: object) -> None:
        if isinstance(widget, ctk.CTkBaseClass):
            widget.bind("<Button-1>", self._handle_click)
            widget.bind("<Enter>", self._handle_enter)
            widget.bind("<Leave>", self._handle_leave)
            for child in widget.winfo_children():
                self._bind_click_handler(child)

    def _handle_click(self, _event: object) -> None:
        if self._command is not None:
            self._command()

    def _handle_enter(self, _event: object) -> None:
        self.configure(fg_color=Theme.PANEL_ALT)

    def _handle_leave(self, _event: object) -> None:
        self.configure(fg_color=Theme.PANEL)
