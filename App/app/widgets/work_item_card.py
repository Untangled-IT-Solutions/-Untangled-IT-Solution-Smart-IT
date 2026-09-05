"""Reusable card for unified Work records."""

from collections.abc import Callable
from typing import Any, Optional

import customtkinter as ctk

from app.models.task import Task
from app.utils.theme import Theme


def _format_due(value: Any) -> str:
    if value is None or value == "":
        return "No due date"
    text = str(value)
    # ISO → readable date
    if "T" in text:
        text = text.split("T", 1)[0]
    return text


class WorkItemCard(ctk.CTkFrame):
    """Displays key information for one task."""

    def __init__(
        self,
        master: object,
        task: Task,
        on_click: Optional[Callable[[Task], None]] = None,
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
            text=self._task.title or "Untitled",
            text_color=Theme.TEXT,
            font=("Segoe UI", 17, "bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="ew")

        ctk.CTkLabel(
            self,
            text=self._task.status or "Pending",
            text_color=Theme.TEXT,
            fg_color=self._status_color(),
            corner_radius=Theme.RADIUS,
            width=124,
            height=28,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=1, padx=18, pady=(16, 4), sticky="e")

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=1, column=0, columnspan=2, padx=18, pady=(4, 8), sticky="ew")
        meta.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="work_meta")

        hours = f"{float(self._task.estimated_hours or 0):g}h allocated"
        self._meta_label(meta, "Assigned to", self._task.assigned_employee or "—", 0)
        self._meta_label(meta, "Category", self._task.category or "—", 1)
        self._meta_label(meta, "Priority", self._task.priority or "Normal", 2)
        self._meta_label(meta, "Due date", _format_due(self._task.due_date), 3)

        # Description preview + hours
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 14), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        desc = (self._task.description or "").strip()
        if desc:
            preview = desc if len(desc) <= 120 else desc[:117] + "…"
            ctk.CTkLabel(
                footer,
                text=preview,
                text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 12),
                anchor="w",
                justify="left",
                wraplength=520,
            ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            footer,
            text=hours,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 11),
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

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
            text=str(value),
            text_color=Theme.TEXT,
            font=("Segoe UI", 13),
            anchor="w",
        ).pack(anchor="w")

    def _bind_click_handler(self, widget: object) -> None:
        widget.bind("<Button-1>", self._handle_click)
        for child in widget.winfo_children():
            self._bind_click_handler(child)

    def _handle_click(self, _event: object = None) -> None:
        if self._on_click is not None:
            self._on_click(self._task)

    def _status_color(self) -> str:
        colors = {
            "New": Theme.ACCENT,
            "Assigned": Theme.PURPLE,
            "In Progress": Theme.WARNING,
            "Waiting Review": Theme.INFO,
            "Completed": Theme.SUCCESS,
            "Cancelled": Theme.DANGER,
        }
        return colors.get(self._task.status, Theme.PANEL_ALT)
