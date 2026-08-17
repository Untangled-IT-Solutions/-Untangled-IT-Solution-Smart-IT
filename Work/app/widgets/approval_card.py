"""Reusable approval request card."""

from collections.abc import Callable

import customtkinter as ctk

from app.models.approval import ApprovalRequest
from app.utils.theme import Theme


class ApprovalCard(ctk.CTkFrame):
    """Displays a concise approval workflow summary."""

    def __init__(
        self,
        master: object,
        request: ApprovalRequest,
        on_click: Callable[[int], None],
    ) -> None:
        super().__init__(
            master,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            corner_radius=Theme.RADIUS,
        )
        self._request = request
        self._on_click = on_click
        self._build_layout()
        self._bind_click_handler(self)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self, text=self._request.title, text_color=Theme.TEXT,
            font=("Segoe UI", 16, "bold"), anchor="w"
        ).grid(row=0, column=0, padx=18, pady=(16, 3), sticky="ew")
        ctk.CTkLabel(
            self, text=self._request.status, text_color=Theme.TEXT,
            fg_color=self._status_color(), corner_radius=Theme.RADIUS,
            width=104, height=26, font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=1, padx=18, pady=(16, 3), sticky="e")
        ctk.CTkLabel(
            self,
            text=f"{self._request.request_type} | {self._request.department}",
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        ).grid(row=1, column=0, columnspan=2, padx=18, sticky="ew")
        ctk.CTkLabel(
            self,
            text=f"Requested by {self._request.requested_by} | {self._request.current_stage}",
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        ).grid(row=2, column=0, columnspan=2, padx=18, pady=(6, 16), sticky="ew")

    def _bind_click_handler(self, widget: object) -> None:
        if isinstance(widget, ctk.CTkBaseClass):
            widget.bind("<Button-1>", self._handle_click)
            for child in widget.winfo_children():
                self._bind_click_handler(child)

    def _handle_click(self, _event: object) -> None:
        if self._request.id is not None:
            self._on_click(self._request.id)

    def _status_color(self) -> str:
        return {
            "Pending": Theme.WARNING,
            "Approved": Theme.SUCCESS,
            "Rejected": Theme.DANGER,
        }.get(self._request.status, Theme.PANEL_ALT)
