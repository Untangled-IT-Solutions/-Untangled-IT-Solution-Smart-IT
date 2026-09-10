"""Reusable card for unified Work records."""

from collections.abc import Callable

import customtkinter as ctk

from app.models.task import Task
from app.utils.theme import Theme


class WorkItemCard(ctk.CTkFrame):
    """Displays key information for one task."""

    def __init__(
        self,
        master: object,
        task: Task,
        on_click: Callable[[int], None] | None = None,
        on_status_change: Callable[[int, str], None] | None = None,
        status_values: list[str] | None = None,
        on_sprint_move: Callable[[int, str], None] | None = None,
        compact: bool = False,
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
        self._on_status_change = on_status_change
        self._status_values = status_values or ["To Do", "In Progress", "In Development", "Completed"]
        self._on_sprint_move = on_sprint_move
        self._compact = compact
        self._build_layout()
        if self._on_click is not None:
            self._bind_click_handler(self)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            self,
            text=self._task.title,
            text_color=Theme.TEXT,
            font=("Segoe UI", 17, "bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, padx=18, pady=(16, 4), sticky="ew")

        self._status = ctk.CTkComboBox(
            self,
            values=self._status_values,
            command=self._handle_status_change,
            state="readonly" if self._on_status_change is not None else "disabled",
            text_color=Theme.TEXT,
            fg_color=self._status_color(),
            border_width=0,
            button_color=self._status_color(),
            button_hover_color=self._status_color(),
            width=112 if self._compact else 150,
            height=28,
            font=("Segoe UI", 12, "bold"),
        )
        self._status.grid(row=0, column=1, padx=18, pady=(16, 4), sticky="e")
        status = self._task.status if self._task.status in self._status.cget("values") else "To Do"
        self._status.set(status)

        detail_row = 1
        if self._task.status == "Inbox":
            ctk.CTkLabel(
                self,
                text=(
                    f"Submitted by {self._task.assigned_by or 'Management'} · "
                    "Awaiting Operations Manager assignment"
                ),
                text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_SMALL,
                anchor="w",
            ).grid(row=1, column=0, columnspan=2, padx=18, pady=(2, 0), sticky="ew")
            detail_row = 2

        reference_parts = []
        if self._task.hardware_serial:
            first_label = "URL" if self._task.category == "Website Merge" else "Serial"
            reference_parts.append(f"{first_label}: {self._task.hardware_serial}")
        if self._task.external_reference:
            if self._task.category == "Website Merge":
                second_label = "Branch"
            elif self._task.category == "Hardware Refurbishment":
                second_label = "Model"
            else:
                second_label = "Reference"
            reference_parts.append(f"{second_label}: {self._task.external_reference}")
        if reference_parts:
            ctk.CTkLabel(
                self,
                text="  |  ".join(reference_parts),
                text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_SMALL,
                anchor="w",
            ).grid(row=detail_row, column=0, columnspan=2, padx=18, pady=(0, 2), sticky="ew")
            detail_row += 1

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=detail_row, column=0, columnspan=2, padx=18, pady=(8, 16), sticky="ew")
        if self._compact:
            meta.grid_columnconfigure((0, 1), weight=1, uniform="work_meta")
            values = (
                ("Owner", self._task.assigned_employee or "Unassigned"),
                ("Priority", self._task.priority),
                ("Estimate", f"{self._task.story_points} pts"),
                ("Due", self._task.due_date or "No due date"),
            )
            for index, (label, value) in enumerate(values):
                self._meta_label(meta, label, value, index % 2, index // 2)
        else:
            meta.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="work_meta")
            self._meta_label(meta, "Assigned Employee", self._task.assigned_employee, 0)
            self._meta_label(meta, "Category", self._task.category, 1)
            self._meta_label(meta, "Priority", self._task.priority, 2)
            self._meta_label(meta, "Due Date", self._task.due_date or "No due date", 3)

        if self._compact and self._on_sprint_move is not None and self._task.id is not None:
            destination = (
                "Next Sprint" if self._task.sprint_bucket == "Current Sprint" else "Current Sprint"
            )
            label = "Defer" if destination == "Next Sprint" else "Pull In"
            ctk.CTkButton(
                self,
                text=label,
                height=30,
                width=86,
                fg_color=Theme.PANEL_ALT,
                hover_color=Theme.BORDER,
                text_color=Theme.TEXT,
                command=lambda: self._on_sprint_move(int(self._task.id), destination),
            ).grid(row=detail_row + 1, column=1, padx=18, pady=(0, 12), sticky="e")

    def _meta_label(
        self, master: object, label: str, value: str, column: int, row: int = 0
    ) -> None:
        container = ctk.CTkFrame(master, fg_color="transparent")
        container.grid(
            row=row, column=column, sticky="ew",
            padx=(0 if column == 0 else 10, 0), pady=(0, 8) if row == 0 else 0,
        )

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
        if widget is self._status or isinstance(widget, ctk.CTkButton):
            return
        if isinstance(widget, ctk.CTkBaseClass):
            widget.bind("<Button-1>", self._handle_click)
            for child in widget.winfo_children():
                self._bind_click_handler(child)

    def _handle_click(self, _event: object) -> None:
        if self._task.id is not None and self._on_click is not None:
            self._on_click(self._task.id)

    def _handle_status_change(self, status: str) -> None:
        color = self._status_color(status)
        self._status.configure(
            fg_color=color,
            button_color=color,
            button_hover_color=color,
        )
        if self._task.id is not None and self._on_status_change is not None:
            self._on_status_change(self._task.id, status)

    def _status_color(self, status: str | None = None) -> str:
        colors = {
            "Inbox": Theme.PURPLE,
            "To Do": Theme.PANEL_ALT,
            "In Progress": Theme.INFO,
            "In Development": Theme.WARNING,
            "In Review": Theme.PURPLE,
            "Completed": Theme.SUCCESS,
            "Cancelled": Theme.DANGER,
            "Archived": Theme.PANEL_ALT,
        }
        return colors.get(status or self._task.status, Theme.PANEL_ALT)
