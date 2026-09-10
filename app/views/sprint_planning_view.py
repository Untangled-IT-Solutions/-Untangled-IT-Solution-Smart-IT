"""Restricted sprint-planning workspace for operational task triage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from app.controllers.task_controller import TaskController
from app.utils.theme import Theme

if TYPE_CHECKING:
    from app.models.account import UserAccount
    from app.models.task import Task


class SprintPlanningView(ctk.CTkFrame):
    """A compact task-dump table for the three sprint-planning super users."""

    def __init__(self, master: object, controller: TaskController,
                 current_account: "UserAccount | None" = None) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._account = current_account
        self._user_name = str(
            getattr(current_account, "full_name", "")
            or getattr(current_account, "username", "")
            or ""
        )
        self._role = str(getattr(current_account, "role", "") or "")
        self._refresh_job: str | None = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_search()
        self._table = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._table.grid(row=2, column=0, sticky="nsew")
        self._table.grid_columnconfigure(0, weight=4)
        self._table.grid_columnconfigure(1, weight=3)
        self._table.grid_columnconfigure(2, weight=2)
        self.refresh()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, pady=(0, 16), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Sprint Planning", text_color=Theme.TEXT,
                     font=Theme.FONT_TITLE).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Central task dump for HR, marketing, development and operations.",
            text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY,
        ).grid(row=1, column=0, pady=(4, 0), sticky="w")
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        ctk.CTkButton(
            actions, text="?  Definitions", command=self._show_definitions,
            height=42, width=126, fg_color=Theme.PANEL_ALT, hover_color=Theme.BORDER,
            text_color=Theme.TEXT, font=Theme.FONT_BUTTON,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            actions, text="+ Add to task dump", command=self._open_task_dump,
            height=42, fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF", font=Theme.FONT_BUTTON,
        ).pack(side="left")

    def _build_search(self) -> None:
        filters = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        filters.grid(row=1, column=0, pady=(0, 14), sticky="ew")
        filters.grid_columnconfigure(0, weight=1)
        self._search = ctk.StringVar()
        entry = ctk.CTkEntry(
            filters, textvariable=self._search, height=40,
            placeholder_text="Search by ticket number, task name, department or keyword…",
            fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER, text_color=Theme.TEXT,
        )
        entry.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        entry.bind("<KeyRelease>", self._schedule_refresh)
        ctk.CTkButton(filters, text="Search", width=82, height=40,
                      command=self.refresh, fg_color=Theme.INFO,
                      hover_color=Theme.ACCENT_HOVER).grid(row=0, column=1, padx=(0, 12))

    def _schedule_refresh(self, _event: object) -> None:
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(220, self.refresh)

    def refresh(self) -> None:
        self._refresh_job = None
        for child in self._table.winfo_children():
            child.destroy()
        self._header_cell("NEW TASKS / TICKETS", 0, "#8B5CF6")
        self._header_cell("ASSIGNED / IN PROGRESS", 1, Theme.INFO)
        self._header_cell("STATUS", 2, Theme.SUCCESS)
        tasks = self._controller.get_tasks(search=self._search.get().strip())
        tasks = [task for task in tasks if task.status not in {"Archived", "Cancelled"}]
        tasks.sort(key=lambda task: (task.status != "Inbox" and bool(task.assigned_employee), task.id or 0))
        if not tasks:
            ctk.CTkLabel(self._table, text="No tasks match your search.",
                         text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY).grid(
                row=1, column=0, columnspan=3, pady=30)
            return
        for row, task in enumerate(tasks, start=1):
            self._task_row(task, row)

    def _header_cell(self, label: str, column: int, color: str) -> None:
        ctk.CTkLabel(self._table, text=label, text_color=color,
                     font=("Segoe UI", 12, "bold"), anchor="w").grid(
            row=0, column=column, padx=(0 if column == 0 else 8, 0), pady=(0, 8), sticky="ew")

    def _task_row(self, task: "Task", row: int) -> None:
        ticket = f"#{task.id:04d}" if task.id is not None else "NEW"
        new_text = f"{ticket}  ·  {task.title}\n{task.department or 'General'} · {task.priority} priority"
        if task.status == "Inbox" or not task.assigned_employee:
            assignment = "Awaiting assignment\nTask dump"
        else:
            assignment = f"{task.assigned_employee}\n{task.category or 'General Operations'}"
        self._cell(new_text, row, 0, Theme.PANEL, command=lambda task_id=task.id: self._edit(task_id))
        self._cell(assignment, row, 1, Theme.PANEL_ALT, command=lambda task_id=task.id: self._edit(task_id))
        status = "New" if task.status == "Inbox" else task.status
        self._cell(status, row, 2, self._status_color(task.status), command=lambda task_id=task.id: self._edit(task_id), bold=True)

    def _cell(self, text: str, row: int, column: int, color: str,
              command: object, bold: bool = False) -> None:
        cell = ctk.CTkButton(
            self._table, text=text, command=command, anchor="w",
            height=58, corner_radius=8, fg_color=color, hover_color=Theme.BORDER,
            text_color=Theme.TEXT, font=("Segoe UI", 12, "bold" if bold else "normal"),
        )
        cell.grid(row=row, column=column, padx=(0 if column == 0 else 8, 0), pady=(0, 7), sticky="ew")

    @staticmethod
    def _status_color(status: str) -> str:
        return {
            "Inbox": Theme.PURPLE, "To Do": Theme.WARNING, "In Progress": Theme.INFO,
            "In Development": "#2563EB", "In Review": Theme.PURPLE,
            "Completed": Theme.SUCCESS,
        }.get(status, Theme.PANEL_ALT)

    def _open_task_dump(self) -> None:
        # Imported here to keep the planning screen independent of the task workspace.
        from app.views.task_view import TaskAssignmentDialog
        TaskAssignmentDialog(
            self, controller=self._controller, assigned_by=self._user_name or "Sprint Planning",
            on_created=self.refresh, allow_assignment=False, planning_submission=True,
            creator_role=self._role or "Super User", default_department="Operations",
            allowed_categories=None,
        )

    def _show_definitions(self) -> None:
        """Explain the four simple planning statuses without leaving the screen."""
        guide = ctk.CTkToplevel(self)
        guide.title("Sprint Planning Definitions")
        guide.configure(fg_color=Theme.BG)
        guide.transient(self.winfo_toplevel())
        guide.grab_set()
        guide.geometry("490x410")
        guide.resizable(False, False)

        content = ctk.CTkFrame(guide, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=28, pady=26)
        ctk.CTkLabel(content, text="Task status guide", text_color=Theme.TEXT,
                     font=Theme.FONT_HEADING).pack(anchor="w")
        ctk.CTkLabel(
            content, text="New  →  To Do  →  In Progress  →  Completed",
            text_color=Theme.ACCENT, font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(8, 18))
        definitions = (
            ("New", "Sitting in the task dump and waiting to be assigned.", Theme.PURPLE),
            ("To Do", "Assigned and ready for someone to start.", Theme.WARNING),
            ("In Progress", "Someone is actively working on it.", Theme.INFO),
            ("Completed", "Finished and ready to be closed or recorded.", Theme.SUCCESS),
        )
        for name, detail, colour in definitions:
            row = ctk.CTkFrame(content, fg_color=Theme.PANEL, corner_radius=8)
            row.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(row, text=name, width=104, height=34, corner_radius=6,
                         fg_color=colour, text_color="#FFFFFF",
                         font=("Segoe UI", 12, "bold")).pack(side="left", padx=8, pady=8)
            ctk.CTkLabel(row, text=detail, text_color=Theme.TEXT,
                         font=Theme.FONT_SMALL, anchor="w").pack(
                             side="left", fill="x", expand=True, padx=(4, 12))
        ctk.CTkButton(content, text="Close", command=guide.destroy, width=90,
                      fg_color=Theme.PANEL_ALT, hover_color=Theme.BORDER,
                      text_color=Theme.TEXT).pack(anchor="e", pady=(8, 0))

    def _edit(self, task_id: int | None) -> None:
        if task_id is None:
            return
        task = self._controller.get_task(task_id)
        if task is None:
            return
        from app.views.task_view import TaskQuickEditDialog
        TaskQuickEditDialog(self, controller=self._controller, task=task,
                            on_saved=self.refresh, allow_management=True,
                            employee_name=self._user_name)
