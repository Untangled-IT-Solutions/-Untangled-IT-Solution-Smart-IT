"""Reusable card for unified Work records."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from app.models.task import Task
from app.utils.theme import Theme


class WorkItemCard(ctk.CTkFrame):
    """Displays key information for one task."""

    def __init__(
        self,
        master: object,
        task: Task,
        on_click: Callable[[Any], None] | None = None,
    ) -> None:
        super().__init__(
            master,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            corner_radius=Theme.RADIUS,
        )
        self._task = task
        self._on_click = on_click
        self._build_layout()
        if self._on_click is not None:
            self._bind_click_handler(self)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            self,
            text=self._task.title,
            text_color=Theme.TEXT,
            font=("Segoe UI", 17, "bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="ew")

        ctk.CTkLabel(
            self,
            text=self._task.status,
            text_color=Theme.TEXT,
            fg_color=self._status_color(),
            corner_radius=Theme.RADIUS,
            width=124,
            height=28,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=1, padx=18, pady=(16, 4), sticky="e")

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=1, column=0, columnspan=2, padx=18, pady=(8, 16), sticky="ew")
        meta.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="work_meta")

        self._meta_label(meta, "Assigned Employee", self._task.assigned_employee, 0)
        self._meta_label(meta, "Category", self._task.category, 1)
        self._meta_label(meta, "Priority", self._task.priority, 2)
        self._meta_label(meta, "Due Date", self._task.due_date or "No due date", 3)
        hours = f"{self._task.actual_hours:g} / {self._task.estimated_hours:g}h"
        if self._task.active_timer_started_at:
            hours = f"Live | {hours}"
        self._meta_label(meta, "Hours", hours, 4)

    def _meta_label(self, master: object, label: str, value: str, column: int) -> None:
        container = ctk.CTkFrame(master, fg_color="transparent")
        container.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 10, 0))

        ctk.CTkLabel(
            container,
            text=label,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 11),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            container,
            text=value or "-",
            text_color=Theme.TEXT,
            font=("Segoe UI", 13),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

    def _bind_click_handler(self, widget: object) -> None:
        if isinstance(widget, ctk.CTkBaseClass):
            widget.bind("<Button-1>", self._handle_click)
            for child in widget.winfo_children():
                self._bind_click_handler(child)

    def _handle_click(self, _event: object) -> None:
        if self._task.id is not None and self._on_click is not None:
            self._on_click(self._task.id)

    def _status_color(self) -> str:
        colors = {
            "Dumped": Theme.ACCENT,
            "Needs Triage": Theme.WARNING,
            "New": Theme.ACCENT,
            "Assigned": Theme.PURPLE,
            "In Progress": Theme.WARNING,
            "Waiting Review": Theme.INFO,
            "Completed": Theme.SUCCESS,
            "Cancelled": Theme.DANGER,
        }
        return colors.get(self._task.status, Theme.PANEL_ALT)
