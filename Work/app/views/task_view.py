"""Tasks workspace view."""

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from app.controllers.task_controller import TaskController
from app.models.task import Task
from app.utils.theme import Theme
from app.widgets.work_item_card import WorkItemCard


class TaskView(ctk.CTkFrame):
    """Shows personal, department, and all task views from unified Work."""

    def __init__(
        self,
        master: object,
        controller: TaskController,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._filters = filters or {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Tasks", text_color=Theme.TEXT, font=Theme.FONT_TITLE).grid(row=0, column=0, sticky="w")
        self.scope = ctk.CTkSegmentedButton(
            header, values=["Inbox", "Reviews", "Overdue", "All", "Personal", "Department"], command=lambda _value: self.refresh(),
            selected_color=Theme.ACCENT, selected_hover_color=Theme.ACCENT_HOVER,
            unselected_color=Theme.PANEL_ALT, unselected_hover_color=Theme.BORDER,
        )
        self.scope.grid(row=0, column=1, sticky="e")
        self.scope.set("Inbox")
        ctk.CTkLabel(self, text="Director and Business Lead task dumps land in Inbox for Operations Manager triage.", text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY).grid(row=1, column=0, pady=(8, 8), sticky="w")
        self.workload_label = ctk.CTkLabel(
            self,
            text="",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12),
            anchor="w",
            justify="left",
        )
        self.workload_label.grid(row=2, column=0, pady=(0, 14), sticky="ew")
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=3, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.refresh()

    def refresh(self) -> None:
        self._update_workload_summary()
        for child in self.list_frame.winfo_children():
            child.destroy()
        tasks = self._controller.get_tasks(self.scope.get())
        if not tasks:
            ctk.CTkLabel(self.list_frame, text="No tasks found.", text_color=Theme.MUTED_TEXT).grid(row=0, column=0, sticky="w")
            return
        for row, task in enumerate(tasks):
            WorkItemCard(self.list_frame, task, self._open_task).grid(row=row, column=0, pady=(0, 12), sticky="ew")

    def _open_task(self, task_id: Any) -> None:
        task = self._controller.get_task(task_id)
        if task is not None:
            TaskActionModal(self, self._controller, task, self.refresh)

    def _update_workload_summary(self) -> None:
        try:
            rows = self._controller.get_workload()
        except Exception:
            self.workload_label.configure(text="")
            return

        if not rows:
            self.workload_label.configure(text="")
            return

        leaders = []
        for row in rows[:4]:
            employee = row.get("employee") or "Unassigned"
            task_count = int(row.get("task_count") or 0)
            estimated = float(row.get("estimated_hours") or 0)
            actual = float(row.get("actual_hours") or 0)
            active = int(row.get("active_now") or 0)
            extra = f", {active} active now" if active else ""
            leaders.append(f"{employee}: {task_count} tasks, {actual:g}/{estimated:g}h{extra}")

        queue_text = ""
        try:
            queue = self._controller.get_decision_queue()
            summary = queue.get("summary") or {}
            queue_text = (
                "Decision queue | "
                f"Inbox {int(summary.get('operations_inbox') or 0)} | "
                f"Reviews {int(summary.get('waiting_review') or 0)} | "
                f"Overdue {int(summary.get('overdue') or 0)} | "
                f"Approvals {int(summary.get('my_approvals') or 0)}"
            )
        except Exception:
            queue_text = ""

        text = "Team workload | " + " | ".join(leaders)
        if queue_text:
            text = f"{queue_text}\n{text}"
        self.workload_label.configure(text=text)


class TaskActionModal(ctk.CTkToplevel):
    """Task details and time actions."""

    def __init__(
        self,
        master: object,
        controller: TaskController,
        task: Task,
        on_updated: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._task = task
        self._on_updated = on_updated
        self.title("Task")
        self.geometry("660x760")
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        panel = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        panel.grid(row=0, column=0, padx=24, pady=24, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel,
            text=self._task.title,
            text_color=Theme.TEXT,
            font=("Segoe UI", 22, "bold"),
            anchor="w",
            wraplength=540,
            justify="left",
        ).grid(row=0, column=0, padx=20, pady=(18, 6), sticky="ew")

        details = (
            f"{self._task.status} | {self._task.priority} | {self._task.category}\n"
            f"Assigned to: {self._task.assigned_employee or '-'}\n"
            f"Due: {self._task.due_date or 'No due date'}\n"
            f"Hours: {self._task.actual_hours:g} actual / {self._task.estimated_hours:g} estimated"
        )
        if self._task.active_timer_started_at:
            details += "\nTimer: running"
        if self._task.director_approval_status:
            details += f"\nDirector approval: {self._task.director_approval_status}"
        if self._task.returned_reason:
            details += f"\nReturned reason: {self._task.returned_reason}"

        ctk.CTkLabel(
            panel,
            text=details,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 13),
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 12), sticky="ew")

        if self._task.description:
            ctk.CTkLabel(
                panel,
                text=self._task.description,
                text_color=Theme.TEXT,
                font=("Segoe UI", 13),
                justify="left",
                wraplength=540,
                anchor="w",
            ).grid(row=2, column=0, padx=20, pady=(0, 14), sticky="ew")

        time_row = ctk.CTkFrame(panel, fg_color="transparent")
        time_row.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
        time_row.grid_columnconfigure(0, weight=1)
        self.hours_entry = ctk.CTkEntry(
            time_row,
            height=38,
            placeholder_text="Hours to log, e.g. 1.5",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
        )
        self.hours_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            time_row,
            text="Log Time",
            width=110,
            height=38,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._log_time,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            panel,
            text="Update note",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12),
            anchor="w",
        ).grid(row=4, column=0, padx=20, pady=(2, 5), sticky="w")
        self.note_entry = ctk.CTkTextbox(
            panel,
            height=80,
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
            border_width=1,
        )
        self.note_entry.grid(row=5, column=0, padx=20, pady=(0, 12), sticky="ew")

        assignment = ctk.CTkFrame(panel, fg_color="transparent")
        assignment.grid(row=6, column=0, padx=20, pady=(0, 12), sticky="ew")
        assignment.grid_columnconfigure(0, weight=1)
        people = self._controller.get_people_names() or [self._task.assigned_employee or ""]
        self.assignee_entry = ctk.CTkOptionMenu(
            assignment,
            values=people,
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
            dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
        )
        if self._task.assigned_employee and self._task.assigned_employee in people:
            self.assignee_entry.set(self._task.assigned_employee)
        elif people:
            self.assignee_entry.set(people[0])
        self.assignee_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            assignment,
            text="Assign",
            width=110,
            height=38,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._assign,
        ).grid(row=0, column=1, sticky="e")

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=7, column=0, padx=20, pady=(0, 18), sticky="ew")
        actions.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(
            actions,
            text="Start",
            height=38,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            command=lambda: self._run_action("start"),
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(
            actions,
            text="Pause",
            height=38,
            fg_color=Theme.WARNING,
            hover_color=Theme.WARNING,
            command=lambda: self._run_action("pause"),
        ).grid(row=0, column=1, padx=6, sticky="ew")
        ctk.CTkButton(
            actions,
            text="Submit Review",
            height=38,
            fg_color=Theme.INFO,
            hover_color=Theme.INFO,
            command=lambda: self._run_action("submit_review"),
        ).grid(row=0, column=2, padx=6, sticky="ew")
        ctk.CTkButton(
            actions,
            text="Complete",
            height=38,
            fg_color=Theme.PURPLE,
            hover_color=Theme.PURPLE,
            command=lambda: self._run_action("complete"),
        ).grid(row=0, column=3, padx=(6, 0), sticky="ew")

        decisions = ctk.CTkFrame(panel, fg_color="transparent")
        decisions.grid(row=8, column=0, padx=20, pady=(0, 18), sticky="ew")
        decisions.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(
            decisions,
            text="Approve Review",
            height=38,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            command=lambda: self._run_decision("approve_review"),
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(
            decisions,
            text="Return",
            height=38,
            fg_color=Theme.WARNING,
            hover_color=Theme.WARNING,
            command=lambda: self._run_decision("return_to_work"),
        ).grid(row=0, column=1, padx=6, sticky="ew")
        ctk.CTkButton(
            decisions,
            text="Ask Director",
            height=38,
            fg_color=Theme.INFO,
            hover_color=Theme.INFO,
            command=lambda: self._run_decision("escalate_to_director"),
        ).grid(row=0, column=2, padx=6, sticky="ew")
        ctk.CTkButton(
            decisions,
            text="Cancel",
            height=38,
            fg_color=Theme.DANGER,
            hover_color=Theme.DANGER_HOVER,
            command=lambda: self._run_decision("cancel"),
        ).grid(row=0, column=3, padx=(6, 0), sticky="ew")

        self.error_label = ctk.CTkLabel(
            panel,
            text="",
            text_color=Theme.DANGER,
            font=("Segoe UI", 12),
            anchor="w",
        )
        self.error_label.grid(row=9, column=0, padx=20, pady=(0, 16), sticky="ew")

    def _note(self) -> str:
        return self.note_entry.get("1.0", "end").strip()

    def _log_time(self) -> None:
        try:
            hours = float(self.hours_entry.get() or 0)
            self._controller.log_time(self._task.id, hours, self._note())
        except Exception as error:
            self.error_label.configure(text=str(error))
            return
        self._finish()

    def _assign(self) -> None:
        try:
            self._controller.assign_task(self._task.id, self.assignee_entry.get())
        except Exception as error:
            self.error_label.configure(text=str(error))
            return
        self._finish()

    def _run_action(self, action: str) -> None:
        try:
            if action == "start":
                self._controller.start_work(self._task.id, self._note())
            elif action == "pause":
                self._controller.pause_work(self._task.id, self._note())
            elif action == "submit_review":
                self._controller.submit_for_review(self._task.id, self._note())
            elif action == "complete":
                self._controller.complete_work(self._task.id, self._note())
        except Exception as error:
            self.error_label.configure(text=str(error))
            return
        self._finish()

    def _run_decision(self, action: str) -> None:
        try:
            if action == "approve_review":
                self._controller.approve_review(self._task.id, self._note())
            elif action == "return_to_work":
                self._controller.return_to_work(self._task.id, self._note())
            elif action == "escalate_to_director":
                self._controller.escalate_to_director(self._task.id, self._note())
            elif action == "cancel":
                self._controller.cancel_task(self._task.id, self._note())
        except Exception as error:
            self.error_label.configure(text=str(error))
            return
        self._finish()

    def _finish(self) -> None:
        self._on_updated()
        self.destroy()
