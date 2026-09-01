"""Reusable employee card."""

from collections.abc import Callable

import customtkinter as ctk

from app.models.employee import Employee
from app.utils.theme import Theme


class EmployeeCard(ctk.CTkFrame):
    """Displays a compact employee summary."""

    def __init__(self, master: object, employee: Employee, on_click: Callable[[int], None]) -> None:
        super().__init__(
            master,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            corner_radius=Theme.RADIUS,
        )
        self._employee = employee
        self._on_click = on_click
        self._build_layout()
        self._bind_click_handler(self)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)

        photo = ctk.CTkLabel(
            self,
            text=self._initials(),
            width=54,
            height=54,
            fg_color=Theme.PANEL_ALT,
            corner_radius=27,
            text_color=Theme.TEXT,
            font=("Segoe UI", 15, "bold"),
        )
        photo.grid(row=0, column=0, rowspan=3, padx=16, pady=16, sticky="n")

        ctk.CTkLabel(
            self,
            text=self._employee.full_name,
            text_color=Theme.TEXT,
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).grid(row=0, column=1, padx=(0, 16), pady=(16, 2), sticky="ew")

        ctk.CTkLabel(
            self,
            text=f"{self._employee.position} | {self._employee.department}",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12),
            anchor="w",
        ).grid(row=1, column=1, padx=(0, 16), sticky="ew")

        status_text = "Clocked In" if self._employee.clocked_in else "Clocked Out"
        ctk.CTkLabel(
            self,
            text=f"{self._employee.status} | {status_text} | {self._employee.current_task}",
            text_color=Theme.TEXT,
            font=("Segoe UI", 12),
            anchor="w",
        ).grid(row=2, column=1, padx=(0, 16), pady=(8, 16), sticky="ew")

    def _bind_click_handler(self, widget: object) -> None:
        """Make the complete card surface select its employee profile."""
        if isinstance(widget, ctk.CTkBaseClass):
            widget.bind("<Button-1>", self._handle_click)
            for child in widget.winfo_children():
                self._bind_click_handler(child)

    def _handle_click(self, _event: object) -> None:
        if self._employee.id is not None:
            self._on_click(self._employee.id)

    def _initials(self) -> str:
        return f"{self._employee.first_name[:1]}{self._employee.last_name[:1]}".upper()
