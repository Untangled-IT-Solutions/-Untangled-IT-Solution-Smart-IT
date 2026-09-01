"""Reusable office request summary card."""

import customtkinter as ctk

from app.models.office_request import OfficeRequest
from app.utils.theme import Theme


class OfficeRequestCard(ctk.CTkFrame):
    """Displays a submitted consumable or equipment request."""

    def __init__(self, master: object, request: OfficeRequest) -> None:
        super().__init__(
            master, fg_color=Theme.PANEL, border_color=Theme.BORDER,
            border_width=1, corner_radius=Theme.RADIUS
        )
        self._request = request
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self, text=f"{self._request.quantity} x {self._request.item_name}", text_color=Theme.TEXT,
            font=("Segoe UI", 16, "bold"), anchor="w"
        ).grid(row=0, column=0, padx=18, pady=(15, 3), sticky="ew")
        ctk.CTkLabel(
            self, text=self._request.approval_status, text_color=Theme.TEXT,
            fg_color={"Pending": Theme.WARNING, "Approved": Theme.SUCCESS, "Rejected": Theme.DANGER}.get(self._request.approval_status, Theme.PANEL_ALT),
            corner_radius=Theme.RADIUS, width=100, height=26, font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=1, padx=18, pady=(15, 3), sticky="e")
        ctk.CTkLabel(
            self, text=f"{self._request.requested_by} | {self._request.department}",
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        ).grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 4), sticky="ew")
        if self._request.notes:
            ctk.CTkLabel(
                self, text=self._request.notes, text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 12), anchor="w", justify="left", wraplength=680
            ).grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 15), sticky="ew")
