"""Tasks workspace with reusable templates and admin assignment controls."""

from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from app.controllers.task_controller import TaskController
from app.models.task_catalog import CATEGORY_DEPARTMENTS, TASK_CATALOG
from app.utils.theme import Theme
from app.widgets.work_item_card import WorkItemCard

if TYPE_CHECKING:
    from app.models.account import UserAccount
    from app.models.task import Task


class TaskView(ctk.CTkFrame):
    """Search, filter, create, assign, and review operational tasks."""

    def __init__(
        self,
        master: object,
        controller: TaskController,
        filters: dict[str, object] | None = None,
        current_account: "UserAccount | None" = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._filters = filters or {}
        self._account = current_account
        self._current_user = str(
            getattr(current_account, "full_name", "")
            or getattr(current_account, "username", "")
            or ""
        )
        self._department = self._controller.get_employee_department(self._current_user)
        self._role = str(getattr(current_account, "role", "Staff") or "Staff")
        self._can_assign = self._controller.can_assign_tasks(
            self._role, self._current_user
        )
        self._can_submit_planning = self._controller.can_submit_planning_tasks(
            self._role, self._current_user
        )
        self._refresh_job: str | None = None
        self._selected_task_id: int | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self._build_header()
        self._build_summary()
        self._build_filters()
        self._build_workstream_bar()
        self._build_scope_bar()

        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.grid(row=5, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        self.refresh()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_group = ctk.CTkFrame(header, fg_color="transparent")
        title_group.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title_group,
            text="TASK MANAGEMENT",
            text_color=Theme.ACCENT,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_group,
            text="Your team's work, untangled.",
            text_color=Theme.TEXT,
            font=Theme.FONT_TITLE,
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            title_group,
            text="Manage priorities, assignments and deadlines from one focused workspace.",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).pack(anchor="w", pady=(4, 0))

        ctk.CTkButton(
            header,
            text=(
                "+  Add Task"
                if self._can_assign
                else (
                    "+  Add Task"
                    if self._can_submit_planning
                    else "+  Add My Task"
                )
            ),
            command=self._open_task_dialog,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=Theme.FONT_BUTTON,
            height=42,
            width=145,
            corner_radius=Theme.RADIUS,
        ).grid(row=0, column=1, sticky="e")

    def _build_summary(self) -> None:
        """Build the four live overview cards used by the task workspace."""
        summary = ctk.CTkFrame(self, fg_color="transparent")
        summary.grid(row=1, column=0, pady=(20, 14), sticky="ew")
        summary.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="task_summary")
        details = (
            ("Total Tasks", "▣", "#DCEEFF", "#1677D2"),
            ("In Progress", "◷", "#FFF0CF", "#D97706"),
            ("Due Today", "▦", "#FFE1E1", "#DC2626"),
            ("Completed", "✓", "#DCF7E2", "#15803D"),
        )
        self._summary_values: list[ctk.CTkLabel] = []
        for column, (label, icon, icon_bg, icon_color) in enumerate(details):
            card = ctk.CTkFrame(
                summary, fg_color=Theme.PANEL, border_color=Theme.BORDER,
                border_width=1, corner_radius=14,
            )
            card.grid(
                row=0, column=column,
                padx=(0 if column == 0 else 6, 0 if column == 3 else 6),
                sticky="ew",
            )
            icon_label = ctk.CTkLabel(
                card, text=icon, width=46, height=46, corner_radius=14,
                fg_color=icon_bg, text_color=icon_color,
                font=("Segoe UI Symbol", 21, "bold"),
            )
            icon_label.pack(side="left", padx=(16, 12), pady=16)
            values = ctk.CTkFrame(card, fg_color="transparent")
            values.pack(side="left", pady=13)
            ctk.CTkLabel(
                values, text=label, text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_SMALL,
            ).pack(anchor="w")
            number = ctk.CTkLabel(
                values, text="0", text_color=Theme.TEXT,
                font=("Segoe UI", 24, "bold"),
            )
            number.pack(anchor="w", pady=(1, 0))
            self._summary_values.append(number)

    def _build_filters(self) -> None:
        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=2, column=0, pady=(0, 10), sticky="ew")
        filters.grid_columnconfigure(0, weight=1)

        self.search_var = ctk.StringVar(value=str(self._filters.get("search") or ""))
        self.search_entry = ctk.CTkEntry(
            filters,
            textvariable=self.search_var,
            placeholder_text="Search tasks, people or categories...",
            height=40,
            border_color=Theme.BORDER,
            fg_color=Theme.PANEL,
            text_color=Theme.TEXT,
        )
        self.search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._schedule_refresh)
        self.search_entry.bind("<Return>", lambda _event: self._run_search())

        ctk.CTkButton(
            filters,
            text="Search",
            command=self._run_search,
            width=76,
            height=40,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF",
        ).grid(row=0, column=1, padx=(0, 8))

        self.category = ctk.CTkComboBox(
            filters,
            values=["All", *TASK_CATALOG.keys()],
            command=self._category_filter_changed,
            state="readonly",
            width=260,
            height=40,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        )
        self.category.grid(row=0, column=2, padx=(0, 8), sticky="e")
        self.category.set("All")

        ctk.CTkButton(
            filters,
            text="Clear",
            command=self._clear_filters,
            width=72,
            height=40,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        ).grid(row=0, column=3, sticky="e")

    def _build_scope_bar(self) -> None:
        scope_row = ctk.CTkFrame(self, fg_color="transparent")
        scope_row.grid(row=4, column=0, pady=(0, 14), sticky="ew")
        scope_row.grid_columnconfigure(1, weight=1)

        # Sprint planning lives in its own restricted workspace.  Keeping it out
        # of the general Tasks screen prevents role-based managers from seeing a
        # second, less controlled planning board.
        scope_values = ["All", "My tasks", "Department"] if self._can_assign else ["My tasks"]
        self.scope = ctk.CTkSegmentedButton(
            scope_row,
            values=scope_values,
            command=lambda _value: self.refresh(),
            selected_color=Theme.ACCENT,
            selected_hover_color=Theme.ACCENT_HOVER,
            unselected_color=Theme.PANEL_ALT,
            unselected_hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        )
        self.scope.grid(row=0, column=0, sticky="w")
        self.scope.set(
            "All" if self._can_assign else "My tasks"
        )

        self.result_label = ctk.CTkLabel(
            scope_row,
            text="",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        )
        self.result_label.grid(row=0, column=1, padx=(14, 0), sticky="e")

    def _build_workstream_bar(self) -> None:
        self.workstream = ctk.CTkSegmentedButton(
            self,
            values=["All work", "Website Merge", "Hardware Refurbishment", "Service & Operations"],
            command=self._workstream_changed,
            selected_color=Theme.ACCENT,
            selected_hover_color=Theme.ACCENT_HOVER,
            unselected_color=Theme.PANEL_ALT,
            unselected_hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        )
        self.workstream.grid(row=3, column=0, pady=(0, 10), sticky="w")
        self.workstream.set("All work")

    def _category_filter_changed(self, _value: str) -> None:
        self.workstream.set("All work")
        self.refresh()

    def _run_search(self) -> None:
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        self.refresh()

    def _clear_filters(self) -> None:
        self.search_var.set("")
        self.category.set("All")
        self.workstream.set("All work")
        self.scope.set(
            "All" if self._can_assign else "My tasks"
        )
        self.refresh()

    def _workstream_changed(self, _value: str) -> None:
        self.category.set("All")
        self.refresh()

    def _schedule_refresh(self, _event: object) -> None:
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(250, self.refresh)

    def refresh(self) -> None:
        self._refresh_job = None
        for child in self.list_frame.winfo_children():
            child.destroy()

        try:
            tasks = self._controller.get_tasks(
                scope=self.scope.get(),
                search=self.search_var.get().strip(),
                category=self.category.get(),
                current_user=self._current_user,
                department=self._department,
                workstream=self.workstream.get(),
            )
        except Exception as exc:
            self.result_label.configure(text="Could not load tasks")
            ctk.CTkLabel(
                self.list_frame,
                text=f"Tasks could not be loaded.\n{exc}",
                text_color=Theme.DANGER,
                justify="left",
            ).grid(row=0, column=0, pady=16, sticky="w")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        overview = (
            len(tasks),
            sum(task.status in {"In Progress", "In Development", "In Review"} for task in tasks),
            sum(task.due_date == today and task.status not in {"Completed", "Archived", "Cancelled"} for task in tasks),
            sum(task.status == "Completed" for task in tasks),
        )
        for label, value in zip(self._summary_values, overview):
            label.configure(text=str(value))

        noun = "task" if len(tasks) == 1 else "tasks"
        self.result_label.configure(text=f"{len(tasks)} {noun}")
        if not tasks:
            empty = ctk.CTkFrame(
                self.list_frame, fg_color=Theme.PANEL, border_color=Theme.BORDER,
                border_width=1, corner_radius=14,
            )
            empty.grid(row=0, column=0, pady=(0, 16), sticky="nsew")
            ctk.CTkLabel(
                empty, text="No tasks match this view", text_color=Theme.TEXT,
                font=Theme.FONT_HEADING,
            ).pack(pady=(70, 6))
            ctk.CTkLabel(
                empty,
                text="Try clearing the filters or add a new task.",
                text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY,
            ).pack(pady=(0, 70))
            return

        task_ids = {int(task.id) for task in tasks if task.id is not None}
        if self._selected_task_id not in task_ids:
            first_id = tasks[0].id
            self._selected_task_id = int(first_id) if first_id is not None else None
        self._render_pipeline(tasks)

    def _render_pipeline(self, tasks: list["Task"]) -> None:
        """Render a Lovable-inspired list and task preview without changing data."""
        workspace = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        workspace.grid(row=0, column=0, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=4, uniform="task_workspace")
        workspace.grid_columnconfigure(1, weight=6, uniform="task_workspace")
        workspace.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            workspace, text="Task pipeline", text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, pady=(0, 8), sticky="w")
        ctk.CTkLabel(
            workspace, text="Selected task details", text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=1, padx=(14, 0), pady=(0, 8), sticky="w")

        pipeline = ctk.CTkScrollableFrame(
            workspace, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=Theme.BORDER,
        )
        pipeline.grid(row=1, column=0, sticky="nsew")
        pipeline.grid_columnconfigure(0, weight=1)
        for row, task in enumerate(tasks):
            self._build_pipeline_card(pipeline, task, row)

        selected = next(
            (task for task in tasks if task.id == self._selected_task_id), tasks[0]
        )
        self._render_task_detail(workspace, selected)

    def _build_pipeline_card(self, master: object, task: "Task", row: int) -> None:
        selected = task.id == self._selected_task_id
        card = ctk.CTkFrame(
            master,
            fg_color=Theme.PANEL,
            border_color=Theme.ACCENT if selected else Theme.BORDER,
            border_width=2 if selected else 1,
            corner_radius=14,
            cursor="hand2",
        )
        card.grid(row=row, column=0, padx=(0, 4), pady=(0, 12), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            card, text=task.title, text_color=Theme.TEXT,
            font=("Segoe UI", 16, "bold"), anchor="w", justify="left",
            wraplength=360, cursor="hand2",
        )
        title.grid(row=0, column=0, padx=16, pady=(14, 5), sticky="ew")
        arrow = ctk.CTkLabel(
            card, text="›", text_color=Theme.ACCENT if selected else Theme.MUTED_TEXT,
            font=("Segoe UI", 25, "bold"), cursor="hand2",
        )
        arrow.grid(row=0, column=1, padx=(4, 16), pady=(10, 0), sticky="e")

        category = ctk.CTkLabel(
            card, text=task.category or "General Operations",
            text_color="#166534", fg_color="#E7F5E8",
            corner_radius=12, height=25, font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        )
        category.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        divider = ctk.CTkFrame(card, fg_color=Theme.BORDER, height=1)
        divider.grid(row=2, column=0, columnspan=2, padx=16, sticky="ew")
        meta = ctk.CTkFrame(card, fg_color="transparent", cursor="hand2")
        meta.grid(row=3, column=0, columnspan=2, padx=16, pady=12, sticky="ew")
        meta.grid_columnconfigure((0, 1), weight=1, uniform="pipeline_meta")
        self._detail_value(meta, "Assignee", task.assigned_employee or "Awaiting assignment", 0, 0)
        self._detail_value(meta, "Due date", task.due_date or "No due date", 0, 1)
        self._detail_value(meta, "Priority", task.priority, 1, 0, self._priority_color(task.priority))
        self._detail_value(meta, "Status", task.status, 1, 1, self._status_color(task.status))

        task_id = int(task.id) if task.id is not None else None
        if task_id is not None:
            callback = lambda _event, value=task_id: self._select_task(value)
            for widget in (card, title, arrow, category, divider, meta):
                widget.bind("<Button-1>", callback)

    def _select_task(self, task_id: int) -> None:
        self._selected_task_id = task_id
        self.refresh()

    def _render_task_detail(self, workspace: object, task: "Task") -> None:
        detail = ctk.CTkScrollableFrame(
            workspace, fg_color=Theme.PANEL, border_color=Theme.BORDER,
            border_width=1, corner_radius=14,
            scrollbar_button_color=Theme.BORDER,
        )
        detail.grid(row=1, column=1, padx=(14, 0), sticky="nsew")
        detail.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(detail, fg_color=Theme.PANEL_ALT, corner_radius=10)
        header.grid(row=0, column=0, padx=8, pady=(8, 16), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text=f"TASK #{int(task.id or 0):03d}", text_color=Theme.ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        ctk.CTkLabel(
            header, text=task.title, text_color=Theme.TEXT,
            font=("Segoe UI", 23, "bold"), anchor="w", justify="left",
            wraplength=610,
        ).grid(row=1, column=0, padx=18, pady=(0, 17), sticky="ew")
        ctk.CTkLabel(
            header, text=task.status, text_color="#FFFFFF",
            fg_color=self._status_color(task.status), corner_radius=14,
            height=28, font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=1, rowspan=2, padx=18, pady=16, sticky="ne")

        body = ctk.CTkFrame(detail, fg_color="transparent")
        body.grid(row=1, column=0, padx=22, pady=(0, 18), sticky="ew")
        body.grid_columnconfigure((0, 1), weight=1, uniform="detail_fields")
        ctk.CTkLabel(
            body, text="Task information", text_color=Theme.TEXT,
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, columnspan=2, pady=(0, 13), sticky="w")
        self._detail_value(body, "Assigned employee", task.assigned_employee or "Awaiting assignment", 1, 0)
        self._detail_value(body, "Category", task.category, 1, 1)
        self._detail_value(body, "Priority", task.priority, 2, 0, self._priority_color(task.priority))
        self._detail_value(body, "Due date", task.due_date or "No due date", 2, 1)
        self._detail_value(body, "Department", task.department or "Not specified", 3, 0)
        self._detail_value(body, "Sprint", task.sprint_bucket, 3, 1)
        self._detail_value(body, "Created by", task.assigned_by or "Not recorded", 4, 0)
        self._detail_value(body, "Estimate", f"{task.story_points} story points", 4, 1)

        row = 5
        if task.description:
            ctk.CTkLabel(
                body, text="Description", text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_SMALL,
            ).grid(row=row, column=0, columnspan=2, pady=(10, 3), sticky="w")
            ctk.CTkLabel(
                body, text=task.description, text_color=Theme.TEXT,
                font=Theme.FONT_BODY, anchor="w", justify="left", wraplength=650,
            ).grid(row=row + 1, column=0, columnspan=2, sticky="ew")
            row += 2

        if task.hardware_serial or task.external_reference:
            separator = ctk.CTkFrame(body, fg_color=Theme.BORDER, height=1)
            separator.grid(row=row, column=0, columnspan=2, pady=(18, 14), sticky="ew")
            row += 1
            ctk.CTkLabel(
                body, text="Internal operations metadata", text_color=Theme.TEXT,
                font=("Segoe UI", 15, "bold"),
            ).grid(row=row, column=0, columnspan=2, sticky="w")
            row += 1
            first_label = "Affected URL" if task.category == "Website Merge" else "Serial number"
            second_label = (
                "Repository branch" if task.category == "Website Merge"
                else "Device model" if task.category == "Hardware Refurbishment"
                else "Reference code"
            )
            self._detail_value(body, first_label, task.hardware_serial or "Not provided", row, 0)
            self._detail_value(body, second_label, task.external_reference or "Not provided", row, 1)
            row += 1

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=row, column=0, columnspan=2, pady=(20, 0), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        can_edit = self._can_assign or (
            task.assigned_employee.strip().casefold() == self._current_user.strip().casefold()
        )
        if can_edit and task.id is not None:
            ctk.CTkButton(
                actions, text="Edit task", width=105, height=38,
                command=lambda: self._open_edit_dialog(int(task.id)),
                fg_color=Theme.PANEL_ALT, hover_color=Theme.BORDER,
                text_color=Theme.TEXT, font=Theme.FONT_BUTTON,
            ).grid(row=0, column=1, padx=(0, 8), sticky="e")
        if task.id is not None:
            status_values = self._status_values(task)
            status = ctk.CTkComboBox(
                actions, values=status_values,
                command=lambda value: self._change_status(int(task.id), value),
                state="readonly" if can_edit else "disabled",
                width=160, height=38, fg_color=self._status_color(task.status),
                border_width=0, button_color=self._status_color(task.status),
                button_hover_color=self._status_color(task.status),
                text_color="#FFFFFF", font=("Segoe UI", 12, "bold"),
            )
            status.grid(row=0, column=2, sticky="e")
            status.set(task.status if task.status in status_values else status_values[0])

    @staticmethod
    def _detail_value(
        master: object, label: str, value: str, row: int, column: int,
        pill_color: str | None = None,
    ) -> None:
        field = ctk.CTkFrame(master, fg_color="transparent")
        field.grid(row=row, column=column, padx=(0, 12), pady=(0, 13), sticky="nw")
        ctk.CTkLabel(
            field, text=label, text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 11),
        ).pack(anchor="w")
        ctk.CTkLabel(
            field, text=value or "-", text_color="#FFFFFF" if pill_color else Theme.TEXT,
            fg_color=pill_color or "transparent", corner_radius=11 if pill_color else 0,
            height=24 if pill_color else 20, font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(3, 0))

    def _status_values(self, task: "Task") -> list[str]:
        if self._can_assign:
            return list(self._controller.WORKFLOW_STATUSES)
        if task.status == "Inbox":
            return ["Inbox", "Cancelled", "Archived"]
        return [
            "To Do", "In Progress", "In Development", "In Review",
            "Completed", "Cancelled", "Archived",
        ]

    @staticmethod
    def _status_color(status: str) -> str:
        return {
            "Inbox": Theme.PURPLE, "To Do": "#64748B",
            "In Progress": "#1677D2", "In Development": "#D97706",
            "In Review": Theme.PURPLE, "Completed": "#15803D",
            "Cancelled": Theme.DANGER, "Archived": "#64748B",
        }.get(status, "#64748B")

    @staticmethod
    def _priority_color(priority: str) -> str:
        return {
            "Low": "#64748B", "Medium": "#D97706", "High": "#DC2626",
            "Critical": "#B91C1C", "Urgent": "#B91C1C",
        }.get(priority, "#64748B")

    def _render_sprint_board(self, tasks: list["Task"]) -> None:
        """Render the Lovable-inspired Current, Next, and Backlog columns."""
        active = [task for task in tasks if task.status not in {"Archived", "Cancelled"}]
        current = [task for task in active if task.sprint_bucket == "Current Sprint"]
        done_points = sum(
            task.story_points for task in current if task.status in {"Completed", "Done"}
        )
        total_points = sum(task.story_points for task in current)
        percent = round((done_points / total_points) * 100) if total_points else 0

        summary = ctk.CTkFrame(
            self.list_frame, fg_color=Theme.PANEL, border_color=Theme.BORDER,
            border_width=1, corner_radius=Theme.RADIUS,
        )
        summary.grid(row=0, column=0, padx=2, pady=(0, 14), sticky="ew")
        summary.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            summary, text="Current Sprint progress", text_color=Theme.TEXT,
            font=("Segoe UI", 15, "bold"),
        ).grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")
        ctk.CTkLabel(
            summary,
            text=f"{done_points}/{total_points} points completed · {percent}%",
            text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL,
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")
        progress = ctk.CTkProgressBar(
            summary,
            height=8,
            corner_radius=4,
            fg_color=Theme.PANEL_ALT,
            progress_color=Theme.ACCENT,
        )
        progress.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="ew")
        progress.set(percent / 100)
        ctk.CTkButton(
            summary, text="Close Sprint", width=110, height=34,
            fg_color=Theme.PANEL_ALT, hover_color=Theme.BORDER,
            text_color=Theme.TEXT, command=self._close_sprint,
        ).grid(row=0, column=1, rowspan=3, padx=14, pady=10, sticky="e")

        board = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        board.grid(row=1, column=0, sticky="ew")
        board.grid_columnconfigure((0, 1, 2), weight=1, uniform="sprint_column")
        column_details = (
            ("Current Sprint", "In flight"),
            ("Next Sprint", "Committed ahead"),
            ("Backlog", "Parked for later"),
        )
        for column_index, (bucket, subtitle) in enumerate(column_details):
            items = [task for task in active if task.sprint_bucket == bucket]
            column = ctk.CTkFrame(
                board, fg_color=Theme.PANEL_ALT, corner_radius=Theme.RADIUS,
            )
            column.grid(
                row=0, column=column_index, padx=(0 if column_index == 0 else 6, 0),
                sticky="nsew",
            )
            column.grid_columnconfigure(0, weight=1)
            points = sum(task.story_points for task in items)
            ctk.CTkLabel(
                column, text=bucket, text_color=Theme.TEXT,
                font=("Segoe UI", 15, "bold"),
            ).grid(row=0, column=0, padx=12, pady=(12, 2), sticky="w")
            ctk.CTkLabel(
                column, text=f"{subtitle} · {len(items)} tasks · {points} pts",
                text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL,
            ).grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")
            if not items:
                ctk.CTkLabel(
                    column, text="Nothing here yet", text_color=Theme.MUTED_TEXT,
                    font=Theme.FONT_SMALL,
                ).grid(row=2, column=0, padx=12, pady=28)
            for item_row, task in enumerate(items, start=2):
                WorkItemCard(
                    column,
                    task,
                    on_click=self._open_edit_dialog,
                    on_status_change=self._change_status,
                    status_values=list(self._controller.WORKFLOW_STATUSES),
                    on_sprint_move=self._move_sprint_task,
                    compact=True,
                ).grid(row=item_row, column=0, padx=8, pady=(0, 10), sticky="ew")

    def _move_sprint_task(self, task_id: int, bucket: str) -> None:
        try:
            self._controller.move_task_to_sprint(task_id, bucket)
        except Exception as exc:
            messagebox.showerror("Task not moved", str(exc), parent=self)
        self.refresh()

    def _close_sprint(self) -> None:
        confirmed = messagebox.askyesno(
            "Close current sprint?",
            "Completed work will be archived, unfinished work deferred, and Next Sprint will become current.",
            parent=self,
        )
        if not confirmed:
            return
        try:
            changed = self._controller.close_sprint()
        except Exception as exc:
            messagebox.showerror("Sprint not closed", str(exc), parent=self)
            return
        messagebox.showinfo("Sprint closed", f"{changed} task(s) rolled forward.", parent=self)
        self.refresh()

    def _open_task_dialog(self) -> None:
        TaskAssignmentDialog(
            self,
            controller=self._controller,
            assigned_by=self._current_user or "Administrator",
            on_created=self.refresh,
            allow_assignment=self._can_assign,
            planning_submission=self._can_submit_planning and not self._can_assign,
            creator_role=self._role,
            default_assignee=self._current_user,
            default_department=self._department,
            allowed_categories=(
                list(TASK_CATALOG.keys())
                if self._can_assign or self._can_submit_planning
                else self._controller.get_self_task_categories(self._department)
            ),
        )

    def _open_edit_dialog(self, task_id: int) -> None:
        task = self._controller.get_task(task_id)
        if task is None:
            messagebox.showerror("Task not found", "This task could not be opened.", parent=self)
            return
        TaskQuickEditDialog(
            self,
            controller=self._controller,
            task=task,
            on_saved=self.refresh,
            allow_management=self._can_assign,
            employee_name=self._current_user,
        )

    def _change_status(self, task_id: int, status: str) -> None:
        try:
            if self._can_assign:
                self._controller.update_status(task_id, status)
            else:
                self._controller.update_self_status(task_id, status, self._current_user)
        except Exception as exc:
            messagebox.showerror("Status not updated", str(exc), parent=self)
        self.refresh()


class TaskAssignmentDialog(ctk.CTkToplevel):
    """Create a self-assigned task or an admin-assigned task."""

    def __init__(
        self,
        master: object,
        controller: TaskController,
        assigned_by: str,
        on_created: object,
        allow_assignment: bool = True,
        planning_submission: bool = False,
        creator_role: str = "Staff",
        default_assignee: str = "",
        default_department: str = "",
        allowed_categories: list[str] | None = None,
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._assigned_by = assigned_by
        self._on_created = on_created
        self._allow_assignment = allow_assignment
        self._planning_submission = planning_submission
        self._creator_role = creator_role
        self._default_assignee = default_assignee
        self._default_department = default_department
        self._allowed_categories = allowed_categories
        self.title(
            "Add and Assign Task"
            if allow_assignment
            else ("Add Sprint Planning Task" if planning_submission else "Add My Task")
        )
        self.configure(fg_color=Theme.BG)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(720, max(400, screen_width - 80))
        height = min(840, max(460, screen_height - 120))
        left = max(20, (screen_width - width) // 2)
        top = max(20, (screen_height - height) // 2 - 20)
        self.geometry(f"{width}x{height}+{left}+{top}")
        self.minsize(min(460, width), min(460, height))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_form()
        self._build_footer()
        self.after(80, self.focus_force)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=24, pady=(22, 12), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=(
                "Add and assign task"
                if self._allow_assignment
                else ("Add sprint planning task" if self._planning_submission else "Add my task")
            ),
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text=(
                "Select a standard task, then choose who is responsible."
                if self._allow_assignment
                else (
                    "Submit this work for Ubuntu to prioritise and assign."
                    if self._planning_submission
                    else "Create a task for yourself and track it through completion."
                )
            ),
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).grid(row=1, column=0, pady=(4, 0), sticky="w")
        ctk.CTkButton(
            header,
            text="Close",
            command=self.destroy,
            width=70,
            height=34,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_form(self) -> None:
        form = ctk.CTkScrollableFrame(
            self,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            corner_radius=Theme.RADIUS,
        )
        form.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nsew")
        form.grid_columnconfigure(0, weight=1)

        categories = self._allowed_categories or list(TASK_CATALOG.keys())
        self.category_var = ctk.StringVar(value=categories[0])
        self.template_var = ctk.StringVar(value=TASK_CATALOG[categories[0]][0])
        self.assignee_var = ctk.StringVar()
        self.department_var = ctk.StringVar(value=CATEGORY_DEPARTMENTS[categories[0]])
        self.priority_var = ctk.StringVar(value="Medium")
        self.sprint_bucket_var = ctk.StringVar(
            value="Backlog" if self._planning_submission else "Current Sprint"
        )
        self.story_points_var = ctk.StringVar(value="3")
        self.due_date_var = ctk.StringVar()
        self.serial_var = ctk.StringVar()
        self.reference_var = ctk.StringVar()

        self._label(form, "Category", 0)
        self.category_input = ctk.CTkComboBox(
            form,
            values=categories,
            variable=self.category_var,
            command=self._category_changed,
            state="readonly",
            height=40,
            fg_color=Theme.BG,
            border_color=Theme.BORDER,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        )
        self.category_input.grid(row=1, column=0, padx=18, sticky="ew")

        self._label(form, "Standard task", 2)
        self.template_input = ctk.CTkComboBox(
            form,
            values=list(TASK_CATALOG[categories[0]]),
            variable=self.template_var,
            command=self._template_changed,
            state="readonly",
            height=40,
            fg_color=Theme.BG,
            border_color=Theme.BORDER,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        )
        self.template_input.grid(row=3, column=0, padx=18, sticky="ew")

        self._label(form, "Task name", 4)
        self.title_input = ctk.CTkEntry(
            form,
            height=40,
            border_color=Theme.BORDER,
            fg_color=Theme.BG,
            text_color=Theme.TEXT,
        )
        self.title_input.grid(row=5, column=0, padx=18, sticky="ew")
        self.title_input.insert(0, self.template_var.get())

        self.description_label = ctk.CTkLabel(
            form,
            text="Description or instructions",
            text_color=Theme.TEXT,
            font=Theme.FONT_SMALL,
        )
        self.description_label.grid(row=6, column=0, padx=18, pady=(14, 5), sticky="w")
        self.description_input = ctk.CTkTextbox(
            form,
            height=90,
            border_color=Theme.BORDER,
            border_width=1,
            fg_color=Theme.BG,
            text_color=Theme.TEXT,
        )
        self.description_input.grid(row=7, column=0, padx=18, sticky="ew")

        references = ctk.CTkFrame(form, fg_color="transparent")
        references.grid(row=8, column=0, padx=18, pady=(14, 0), sticky="ew")
        references.grid_columnconfigure((0, 1), weight=1)
        self.detail_one_label = ctk.CTkLabel(references, text="Related asset or URL (optional)", text_color=Theme.TEXT, font=Theme.FONT_SMALL)
        self.detail_one_label.grid(row=0, column=0, sticky="w")
        self.detail_two_label = ctk.CTkLabel(references, text="Ticket/reference (optional)", text_color=Theme.TEXT, font=Theme.FONT_SMALL)
        self.detail_two_label.grid(row=0, column=1, padx=(10, 0), sticky="w")
        self.detail_one_input = ctk.CTkEntry(
            references,
            textvariable=self.serial_var,
            placeholder_text="e.g. PF4X92K1",
            height=40,
            border_color=Theme.BORDER,
            fg_color=Theme.BG,
            text_color=Theme.TEXT,
        )
        self.detail_one_input.grid(row=1, column=0, sticky="ew")
        self.detail_two_input = ctk.CTkEntry(
            references,
            textvariable=self.reference_var,
            placeholder_text="e.g. PR-142 or TKT-0081",
            height=40,
            border_color=Theme.BORDER,
            fg_color=Theme.BG,
            text_color=Theme.TEXT,
        )
        self.detail_two_input.grid(row=1, column=1, padx=(10, 0), sticky="ew")

        employees = self._controller.get_employee_names() if self._allow_assignment else []
        if self._allow_assignment:
            employee_values = employees or ["No employees available"]
        elif self._planning_submission:
            employee_values = ["Unassigned — Sprint Planning"]
        else:
            employee_values = [self._default_assignee or "Current employee unavailable"]
        self.assignee_var.set(employee_values[0])
        self._label(
            form,
            "Assign to"
            if self._allow_assignment
            else ("Planning queue" if self._planning_submission else "Assigned to me"),
            9,
        )
        self.assignee_input = ctk.CTkComboBox(
            form,
            values=employee_values,
            variable=self.assignee_var,
            state="readonly",
            height=40,
            fg_color=Theme.BG,
            border_color=Theme.BORDER,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        )
        self.assignee_input.grid(row=10, column=0, padx=18, sticky="ew")
        if not self._allow_assignment:
            self.assignee_input.configure(state="disabled")

        departments = self._controller.get_departments()
        department_values = sorted(set(departments) | set(CATEGORY_DEPARTMENTS.values()), key=str.lower)
        self._label(form, "Department", 11)
        self.department_input = ctk.CTkComboBox(
            form,
            values=department_values,
            variable=self.department_var,
            state="readonly",
            height=40,
            fg_color=Theme.BG,
            border_color=Theme.BORDER,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        )
        self.department_input.grid(row=12, column=0, padx=18, sticky="ew")
        if (
            self._default_department
            and not self._allow_assignment
            and not self._planning_submission
        ):
            self.department_var.set(self._default_department)

        two_columns = ctk.CTkFrame(form, fg_color="transparent")
        two_columns.grid(row=13, column=0, padx=18, pady=(14, 0), sticky="ew")
        two_columns.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(two_columns, text="Due date (YYYY-MM-DD)", text_color=Theme.TEXT, font=Theme.FONT_SMALL).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(two_columns, text="Priority", text_color=Theme.TEXT, font=Theme.FONT_SMALL).grid(row=0, column=1, padx=(10, 0), sticky="w")
        ctk.CTkEntry(
            two_columns,
            textvariable=self.due_date_var,
            placeholder_text="2026-08-30",
            height=40,
            border_color=Theme.BORDER,
            fg_color=Theme.BG,
            text_color=Theme.TEXT,
        ).grid(row=1, column=0, sticky="ew")
        ctk.CTkComboBox(
            two_columns,
            values=["Low", "Medium", "High", "Critical", "Urgent"],
            variable=self.priority_var,
            state="readonly",
            height=40,
            fg_color=Theme.BG,
            border_color=Theme.BORDER,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        ).grid(row=1, column=1, padx=(10, 0), sticky="ew")

        ctk.CTkLabel(
            two_columns, text="Plan into", text_color=Theme.TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=2, column=0, pady=(12, 0), sticky="w")
        ctk.CTkLabel(
            two_columns, text="Estimate (story points)", text_color=Theme.TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=2, column=1, padx=(10, 0), pady=(12, 0), sticky="w")
        ctk.CTkComboBox(
            two_columns,
            values=list(self._controller.SPRINT_BUCKETS),
            variable=self.sprint_bucket_var,
            state="readonly",
            height=40,
            fg_color=Theme.BG,
            border_color=Theme.BORDER,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        ).grid(row=3, column=0, pady=(4, 0), sticky="ew")
        ctk.CTkComboBox(
            two_columns,
            values=["1", "2", "3", "5", "8", "13"],
            variable=self.story_points_var,
            state="readonly",
            height=40,
            fg_color=Theme.BG,
            border_color=Theme.BORDER,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        ).grid(row=3, column=1, padx=(10, 0), pady=(4, 0), sticky="ew")

        self._can_create = self._planning_submission or employee_values[0] not in {
            "No employees available",
            "Current employee unavailable",
        }
        self._configure_category_fields(categories[0])

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        footer.grid(row=2, column=0, padx=24, pady=(0, 20), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            footer,
            text=(
                "Required: category and task name; Ubuntu assigns the employee later"
                if self._planning_submission
                else "Required: category, task name and assignee"
            ),
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=0, column=0, padx=16, pady=14, sticky="w")
        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.grid(row=0, column=1, padx=14, pady=8, sticky="e")
        ctk.CTkButton(
            actions,
            text="Cancel",
            command=self.destroy,
            width=90,
            height=40,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        ).pack(side="left", padx=(0, 8))
        self.create_button = ctk.CTkButton(
            actions,
            text=(
                "Create task"
                if self._allow_assignment
                else ("Send to planning" if self._planning_submission else "Create my task")
            ),
            command=self._create_task,
            width=125,
            height=40,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=Theme.FONT_BUTTON,
        )
        self.create_button.pack(side="left")
        if not self._can_create:
            self.create_button.configure(state="disabled")

    @staticmethod
    def _label(master: object, text: str, row: int) -> None:
        ctk.CTkLabel(master, text=text, text_color=Theme.TEXT, font=Theme.FONT_SMALL).grid(
            row=row,
            column=0,
            padx=18,
            pady=(14, 5),
            sticky="w",
        )

    def _category_changed(self, category: str) -> None:
        templates = list(TASK_CATALOG[category])
        self.template_input.configure(values=templates)
        self.template_var.set(templates[0])
        self.department_var.set(CATEGORY_DEPARTMENTS[category])
        self._set_title(templates[0])
        self._configure_category_fields(category)

    def _configure_category_fields(self, category: str) -> None:
        if category == "Hardware Refurbishment":
            self.description_label.configure(text="Hardware component issues")
            self.detail_one_label.configure(text="Serial number")
            self.detail_two_label.configure(text="Laptop model")
            self.detail_one_input.configure(placeholder_text="e.g. PF4X92K1")
            self.detail_two_input.configure(placeholder_text="e.g. Lenovo ThinkPad T14")
        elif category == "Website Merge":
            self.description_label.configure(text="Bug description")
            self.detail_one_label.configure(text="Affected URL")
            self.detail_two_label.configure(text="Repository branch")
            self.detail_one_input.configure(placeholder_text="e.g. /checkout or full URL")
            self.detail_two_input.configure(placeholder_text="e.g. feature/catalog-merge")
        else:
            self.description_label.configure(text="Description or instructions")
            self.detail_one_label.configure(text="Related asset or URL (optional)")
            self.detail_two_label.configure(text="Ticket/reference (optional)")
            self.detail_one_input.configure(placeholder_text="Optional")
            self.detail_two_input.configure(placeholder_text="e.g. TKT-0081")

    def _template_changed(self, task_name: str) -> None:
        self._set_title(task_name)

    def _set_title(self, value: str) -> None:
        self.title_input.delete(0, "end")
        self.title_input.insert(0, value)

    def _create_task(self) -> None:
        due_date = self.due_date_var.get().strip()
        if due_date:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid due date", "Enter the due date as YYYY-MM-DD.", parent=self)
                return

        assignee = self.assignee_var.get().strip()
        if (
            not self._planning_submission
            and (not assignee or assignee == "No employees available")
        ):
            messagebox.showerror("Employee required", "Add an employee before assigning this task.", parent=self)
            return

        try:
            payload = {
                "title": self.title_input.get().strip(),
                "description": self.description_input.get("1.0", "end").strip(),
                "assigned_employee": assignee,
                "assigned_by": self._assigned_by,
                "priority": self.priority_var.get(),
                "department": self.department_var.get(),
                "due_date": due_date,
                "category": self.category_var.get(),
                "hardware_serial": self.serial_var.get().strip(),
                "external_reference": self.reference_var.get().strip(),
                "sprint_bucket": self.sprint_bucket_var.get(),
                "story_points": int(self.story_points_var.get()),
            }
            if self._allow_assignment:
                self._controller.create_task(payload)
            elif self._planning_submission:
                self._controller.create_planning_task(
                    payload,
                    creator_name=self._assigned_by,
                    creator_role=self._creator_role,
                )
            else:
                self._controller.create_self_task(
                    payload,
                    employee_name=self._default_assignee,
                    department=self._default_department,
                )
        except Exception as exc:
            messagebox.showerror("Task not created", f"The task could not be created.\n\n{exc}", parent=self)
            return

        messagebox.showinfo(
            "Task assigned" if self._allow_assignment else "Task sent to Sprint Planning",
            (
                f"{self.title_input.get().strip()} was assigned to {assignee}."
                if self._allow_assignment
                else (
                    "The task is now waiting in Sprint Planning for Ubuntu to assign."
                    if self._planning_submission
                    else "Your task was saved in Sprint Planning for manager review."
                )
            ),
            parent=self,
        )
        if callable(self._on_created):
            self._on_created()
        self.destroy()


class TaskQuickEditDialog(ctk.CTkToplevel):
    """Compact editor opened by clicking a task row."""

    def __init__(
        self,
        master: object,
        controller: TaskController,
        task: "Task",
        on_saved: object,
        allow_management: bool = True,
        employee_name: str = "",
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._task = task
        self._on_saved = on_saved
        self._allow_management = allow_management
        self._employee_name = employee_name
        self.title("Quick Edit Task")
        self.configure(fg_color=Theme.BG)
        self.transient(master.winfo_toplevel())
        self.grab_set()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(620, max(400, screen_width - 80))
        height = min(760, max(460, screen_height - 120))
        left = max(20, (screen_width - width) // 2)
        top = max(20, (screen_height - height) // 2 - 20)
        self.geometry(f"{width}x{height}+{left}+{top}")
        self.minsize(min(440, width), min(460, height))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=24, pady=(22, 12), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Quick edit", text_color=Theme.TEXT, font=Theme.FONT_HEADING).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text=task.title, text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY, anchor="w").grid(row=1, column=0, pady=(4, 0), sticky="ew")
        ctk.CTkButton(
            header,
            text="Close",
            command=self.destroy,
            width=70,
            height=34,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        form = ctk.CTkScrollableFrame(
            self,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            corner_radius=Theme.RADIUS,
        )
        form.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nsew")
        form.grid_columnconfigure(0, weight=1)

        employees = self._controller.get_employee_names() if self._allow_management else []
        employee_values = sorted(set(employees + [task.assigned_employee]), key=str.lower)
        departments = self._controller.get_departments() if self._allow_management else []
        department_values = sorted(set(departments + [task.department]) | set(CATEGORY_DEPARTMENTS.values()), key=str.lower)

        self.assignee_var = ctk.StringVar(value=task.assigned_employee)
        self.department_var = ctk.StringVar(value=task.department)
        self.due_date_var = ctk.StringVar(value=task.due_date)
        self.priority_var = ctk.StringVar(value=task.priority)
        self.sprint_bucket_var = ctk.StringVar(value=task.sprint_bucket)
        self.story_points_var = ctk.StringVar(value=str(task.story_points))
        current_status = task.status if task.status in self._controller.WORKFLOW_STATUSES else "To Do"
        self.status_var = ctk.StringVar(value=current_status)
        self.serial_var = ctk.StringVar(value=task.hardware_serial)
        self.reference_var = ctk.StringVar(value=task.external_reference)

        if self._allow_management:
            status_values = list(self._controller.WORKFLOW_STATUSES)
        elif task.status == "Inbox":
            status_values = ["Inbox", "Cancelled", "Archived"]
        else:
            status_values = ["To Do", "In Progress", "In Development", "In Review", "Completed", "Cancelled", "Archived"]
        fields = (
            ("Assignee", self.assignee_var, employee_values or [task.assigned_employee or "Unassigned"]),
            ("Department", self.department_var, department_values),
            ("Priority", self.priority_var, ["Low", "Medium", "High", "Critical", "Urgent"]),
            ("Status", self.status_var, status_values),
            ("Sprint", self.sprint_bucket_var, list(self._controller.SPRINT_BUCKETS)),
            ("Story points", self.story_points_var, ["1", "2", "3", "5", "8", "13"]),
        )
        row = 0
        for label, variable, values in fields:
            TaskAssignmentDialog._label(form, label, row)
            combo = ctk.CTkComboBox(
                form,
                values=values,
                variable=variable,
                state="readonly",
                height=40,
                fg_color=Theme.BG,
                border_color=Theme.BORDER,
                button_color=Theme.ACCENT,
                button_hover_color=Theme.ACCENT_HOVER,
                text_color=Theme.TEXT,
            )
            combo.grid(row=row + 1, column=0, padx=18, sticky="ew")
            if not self._allow_management and label in {
                "Assignee", "Department", "Sprint", "Story points"
            }:
                combo.configure(state="disabled")
            row += 2

        TaskAssignmentDialog._label(form, "Due date (YYYY-MM-DD)", row)
        ctk.CTkEntry(
            form,
            textvariable=self.due_date_var,
            height=40,
            border_color=Theme.BORDER,
            fg_color=Theme.BG,
            text_color=Theme.TEXT,
        ).grid(row=row + 1, column=0, padx=18, sticky="ew")
        row += 2

        first_detail_label = "Affected URL" if task.category == "Website Merge" else "Hardware serial"
        second_detail_label = (
            "Repository branch" if task.category == "Website Merge"
            else "Laptop model" if task.category == "Hardware Refurbishment"
            else "Ticket or external reference"
        )
        TaskAssignmentDialog._label(form, first_detail_label, row)
        ctk.CTkEntry(
            form,
            textvariable=self.serial_var,
            placeholder_text="Optional for hardware tasks",
            height=40,
            border_color=Theme.BORDER,
            fg_color=Theme.BG,
            text_color=Theme.TEXT,
        ).grid(row=row + 1, column=0, padx=18, sticky="ew")
        row += 2

        TaskAssignmentDialog._label(form, second_detail_label, row)
        ctk.CTkEntry(
            form,
            textvariable=self.reference_var,
            placeholder_text="e.g. PR-142 or TKT-0081",
            height=40,
            border_color=Theme.BORDER,
            fg_color=Theme.BG,
            text_color=Theme.TEXT,
        ).grid(row=row + 1, column=0, padx=18, sticky="ew")

        actions = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        actions.grid(row=2, column=0, padx=24, pady=(0, 20), sticky="e")
        if self._allow_management:
            ctk.CTkButton(
                actions,
                text="Delete task",
                command=self._delete,
                width=100,
                height=40,
                fg_color=Theme.DANGER,
                hover_color=Theme.DANGER_HOVER,
                text_color="#FFFFFF",
            ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Cancel",
            command=self.destroy,
            width=90,
            height=40,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Save changes",
            command=self._save,
            width=130,
            height=40,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=Theme.FONT_BUTTON,
        ).pack(side="left")

    def _save(self) -> None:
        due_date = self.due_date_var.get().strip()
        if due_date:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid due date", "Enter the due date as YYYY-MM-DD.", parent=self)
                return
        try:
            task_id = int(self._task.id)
            payload = {
                "assigned_employee": self.assignee_var.get().strip(),
                "department": self.department_var.get().strip(),
                "due_date": due_date,
                "priority": self.priority_var.get(),
                "status": self.status_var.get(),
                "hardware_serial": self.serial_var.get().strip(),
                "external_reference": self.reference_var.get().strip(),
                "sprint_bucket": self.sprint_bucket_var.get(),
                "story_points": int(self.story_points_var.get()),
            }
            if self._allow_management:
                self._controller.update_task(task_id, payload)
            else:
                self._controller.update_self_task(task_id, payload, self._employee_name)
                if self.status_var.get() != self._task.status:
                    self._controller.update_self_status(task_id, self.status_var.get(), self._employee_name)
        except Exception as exc:
            messagebox.showerror("Task not updated", str(exc), parent=self)
            return
        if callable(self._on_saved):
            self._on_saved()
        self.destroy()

    def _delete(self) -> None:
        if not self._allow_management:
            return
        confirmed = messagebox.askyesno(
            "Delete task permanently?",
            (
                f"Delete '{self._task.title}'?\n\n"
                "This removes the task from the workspace. Use Archived instead "
                "when the record should remain available for audit purposes."
            ),
            icon="warning",
            parent=self,
        )
        if not confirmed:
            return
        try:
            self._controller.delete_task(int(self._task.id))
        except Exception as exc:
            messagebox.showerror("Task not deleted", str(exc), parent=self)
            return
        if callable(self._on_saved):
            self._on_saved()
        self.destroy()
