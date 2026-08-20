"""Unified Work page view."""

from collections.abc import Callable
from datetime import date, timedelta

import customtkinter as ctk

from app.controllers.work_controller import WorkController
from app.models.task import Task
from app.utils.theme import Theme
from app.utils.timezone import utc_to_local
from app.widgets.work_item_card import WorkItemCard


class WorkView(ctk.CTkFrame):
    """Displays the unified Work backlog, filters, and editable Work records."""

    def __init__(
        self,
        master: object,
        controller: WorkController,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._initial_filters = filters or {}
        self._list_frame: ctk.CTkScrollableFrame | None = None
        self._build_layout()
        self._apply_initial_filters()
        self.refresh()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Work", text_color=Theme.TEXT, font=("Segoe UI", 30, "bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="New Work",
            height=40,
            width=128,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._open_new_work_modal,
        ).grid(row=0, column=1, sticky="e")

        filters = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        filters.grid(row=1, column=0, pady=(20, 18), sticky="ew")
        filters.grid_columnconfigure(0, weight=2)
        filters.grid_columnconfigure((1, 2, 3, 4, 5), weight=1)
        self.search_entry = ctk.CTkEntry(
            filters,
            height=38,
            placeholder_text="Search work",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
        )
        self.search_entry.grid(row=0, column=0, padx=14, pady=14, sticky="ew")
        self.search_entry.bind("<KeyRelease>", lambda _event: self.refresh())
        self.employee_filter = self._filter_menu(
            filters, ["All", *self._controller.get_employee_names()], 1
        )
        self.category_filter = self._filter_menu(filters, self._controller.get_categories(), 2)
        self.department_filter = self._filter_menu(filters, self._controller.get_departments(), 3)
        self.priority_filter = self._filter_menu(filters, self._controller.get_priorities(), 4)
        self.status_filter = self._filter_menu(filters, self._controller.get_statuses(), 5)

        self._list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._list_frame.grid(row=2, column=0, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

    def refresh(self) -> None:
        """Reload Work cards from SQLite using the selected filters."""
        if self._list_frame is None:
            return
        for child in self._list_frame.winfo_children():
            child.destroy()
        tasks = self._controller.get_all_work(
            search=self.search_entry.get(),
            assigned_employee=self.employee_filter.get(),
            category=self.category_filter.get(),
            department=self.department_filter.get(),
            priority=self.priority_filter.get(),
            status=self.status_filter.get(),
        )
        tasks = self._apply_due_filter(tasks)
        if not tasks:
            self._show_empty_state()
            return
        for row, task in enumerate(tasks):
            WorkItemCard(self._list_frame, task, self._open_work_detail).grid(
                row=row, column=0, sticky="ew", pady=(0, 12)
            )

    def _filter_menu(self, master: object, values: list[str], column: int) -> ctk.CTkOptionMenu:
        menu = ctk.CTkOptionMenu(
            master,
            values=values or ["All"],
            height=38,
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
            dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
            command=lambda _value: self.refresh(),
        )
        menu.set((values or ["All"])[0])
        menu.grid(row=0, column=column, padx=(0, 14), pady=14, sticky="ew")
        return menu

    def _apply_initial_filters(self) -> None:
        self._set_menu_if_available(self.category_filter, self._initial_filters.get("category"))
        self._set_menu_if_available(self.department_filter, self._initial_filters.get("department"))
        self._set_menu_if_available(self.status_filter, self._initial_filters.get("status"))

    @staticmethod
    def _set_menu_if_available(menu: ctk.CTkOptionMenu, value: object) -> None:
        if isinstance(value, str) and value in menu.cget("values"):
            menu.set(value)

    def _apply_due_filter(self, tasks: list[Task]) -> list[Task]:
        due_filter = self._initial_filters.get("due_filter")
        if not isinstance(due_filter, str) or due_filter == "All":
            return tasks

        today = date.today()
        if due_filter == "Today":
            return [task for task in tasks if task.due_date == today.isoformat()]
        if due_filter == "Overdue":
            return [
                task for task in tasks
                if task.due_date and task.due_date < today.isoformat() and task.status != "Completed"
            ]
        if due_filter == "This Week":
            week_end = today + timedelta(days=6)
            return [
                task for task in tasks
                if today.isoformat() <= task.due_date <= week_end.isoformat()
            ]
        return tasks

    def _show_empty_state(self) -> None:
        empty_state = ctk.CTkFrame(
            self._list_frame,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            corner_radius=Theme.RADIUS,
        )
        empty_state.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            empty_state, text="No work found", text_color=Theme.TEXT, font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(
            empty_state,
            text="Adjust filters or create a Work item.",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 13),
        ).pack(anchor="w", padx=20, pady=(0, 20))

    def _open_new_work_modal(self) -> None:
        WorkFormModal(self, self._controller, self.refresh)

    def _open_work_detail(self, task_id: int) -> None:
        task = self._controller.get_work(task_id)
        if task is not None:
            WorkFormModal(self, self._controller, self.refresh, task)


class WorkFormModal(ctk.CTkToplevel):
    """Reusable create and edit form for a unified Work record."""

    def __init__(
        self,
        master: object,
        controller: WorkController,
        on_saved: Callable[[], None],
        task: Task | None = None,
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._on_saved = on_saved
        self._task = task
        self.title("Edit Work" if task is not None else "New Work")
        self.geometry("680x840")
        self.minsize(620, 700)
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        heading = "Edit Work" if self._task is not None else "New Work"
        ctk.CTkLabel(
            self, text=heading, text_color=Theme.TEXT, font=("Segoe UI", 26, "bold")
        ).grid(row=0, column=0, padx=28, pady=(24, 10), sticky="w")
        form = ctk.CTkScrollableFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        form.grid(row=1, column=0, padx=28, sticky="nsew")
        form.grid_columnconfigure(0, weight=1)

        self.title_entry = self._entry(form, "Task Name", 0)
        self.description_entry = self._textbox(form, "Description", 1, 80)
        self.category_entry = self._option(form, "Category", self._controller.get_categories()[1:], 2)
        self.assigned_employee_entry = self._option(
            form, "Assign Employee", self._controller.get_employee_names(), 3
        )
        self.department_entry = self._option(form, "Department", self._controller.get_departments()[1:], 4)
        self.priority_entry = self._option(form, "Priority", list(self._controller.PRIORITIES), 5)
        self.status_entry = self._option(form, "Status", list(self._controller.STATUSES), 6)
        self.start_date_entry = self._entry(form, "Start Date", 7, "YYYY-MM-DD")
        self.due_date_entry = self._entry(form, "Due Date", 8, "YYYY-MM-DD")
        self.estimated_hours_entry = self._entry(form, "Estimated Hours", 9, "0")
        self.actual_hours_entry = self._entry(form, "Actual Hours", 10, "0")
        self.checklist_entry = self._textbox(form, "Checklist (one item per line)", 11, 80)
        self.comments_entry = self._textbox(form, "Comments", 12, 80)
        self.attachments_entry = self._entry(form, "Attachments (placeholder)", 13, "Reference or filename")
        if self._task is not None:
            self._history_section(form, 14)
        self._load_task()

        self.error_label = ctk.CTkLabel(self, text="", text_color=Theme.DANGER, font=("Segoe UI", 13))
        self.error_label.grid(row=2, column=0, padx=28, pady=(10, 0), sticky="w")
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, padx=28, pady=(12, 22), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        if self._task is not None:
            ctk.CTkButton(
                actions,
                text="Delete",
                width=100,
                fg_color=Theme.DANGER,
                hover_color=Theme.DANGER_HOVER,
                command=self._delete,
            ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            actions,
            text="Cancel",
            width=100,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            command=self.destroy,
        ).grid(row=0, column=1, padx=(0, 10), sticky="e")
        ctk.CTkButton(
            actions,
            text="Save",
            width=100,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._save,
        ).grid(row=0, column=2, sticky="e")

    def _load_task(self) -> None:
        if self._task is None:
            self.status_entry.set(self._controller.DEFAULT_STATUS)
            self.title_entry.focus_set()
            return
        task = self._task
        self.title_entry.insert(0, task.title)
        self.description_entry.insert("1.0", task.description)
        self.category_entry.set(task.category)
        self.assigned_employee_entry.set(task.assigned_employee)
        self.department_entry.set(task.department)
        self.priority_entry.set(task.priority)
        self.status_entry.set(task.status)
        self.start_date_entry.insert(0, task.start_date)
        self.due_date_entry.insert(0, task.due_date)
        self.estimated_hours_entry.insert(0, str(task.estimated_hours))
        self.actual_hours_entry.insert(0, str(task.actual_hours))
        self.checklist_entry.insert("1.0", self._controller.checklist_text(task))
        self.comments_entry.insert("1.0", task.comments)
        self.attachments_entry.insert(0, task.attachments if task.attachments != "[]" else "")

    def _entry(self, master: object, label: str, row: int, placeholder: str = "") -> ctk.CTkEntry:
        self._field_label(master, label, row)
        entry = ctk.CTkEntry(
            master, height=40, placeholder_text=placeholder or label, border_color=Theme.BORDER, fg_color=Theme.PANEL_ALT
        )
        entry.grid(row=(row * 2) + 1, column=0, padx=20, pady=(0, 12), sticky="ew")
        return entry

    def _textbox(self, master: object, label: str, row: int, height: int) -> ctk.CTkTextbox:
        self._field_label(master, label, row)
        textbox = ctk.CTkTextbox(
            master, height=height, border_color=Theme.BORDER, border_width=1, fg_color=Theme.PANEL_ALT
        )
        textbox.grid(row=(row * 2) + 1, column=0, padx=20, pady=(0, 12), sticky="ew")
        return textbox

    def _option(self, master: object, label: str, values: list[str], row: int) -> ctk.CTkOptionMenu:
        self._field_label(master, label, row)
        menu_values = values or [""]
        option = ctk.CTkOptionMenu(
            master, values=menu_values, height=40, fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT, button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT, dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL, dropdown_hover_color=Theme.PANEL_ALT
        )
        option.set(menu_values[0])
        option.grid(row=(row * 2) + 1, column=0, padx=20, pady=(0, 12), sticky="ew")
        return option

    def _field_label(self, master: object, text: str, row: int) -> None:
        ctk.CTkLabel(
            master, text=text, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12)
        ).grid(row=row * 2, column=0, padx=20, pady=(10 if row == 0 else 0, 5), sticky="w")

    def _history_section(self, master: object, row: int) -> None:
        self._field_label(master, "History", row)
        history = self._controller.get_history(self._task.id)
        history_text = "\n".join(
            f"{utc_to_local(item.created_at) if item.created_at else ''} | {item.action}: {item.note}"
            for item in history
        ) or "No recorded history."
        ctk.CTkLabel(
            master, text=history_text, text_color=Theme.MUTED_TEXT,
            justify="left", anchor="w", wraplength=570, font=("Segoe UI", 12)
        ).grid(row=(row * 2) + 1, column=0, padx=20, pady=(0, 14), sticky="ew")

    def _save(self) -> None:
        values = {
            "title": self.title_entry.get(),
            "description": self.description_entry.get("1.0", "end").strip(),
            "category": self.category_entry.get(),
            "assigned_employee": self.assigned_employee_entry.get(),
            "department": self.department_entry.get(),
            "priority": self.priority_entry.get(),
            "status": self.status_entry.get(),
            "start_date": self.start_date_entry.get(),
            "due_date": self.due_date_entry.get(),
            "estimated_hours": self.estimated_hours_entry.get(),
            "actual_hours": self.actual_hours_entry.get(),
            "checklist": self.checklist_entry.get("1.0", "end").strip(),
            "comments": self.comments_entry.get("1.0", "end").strip(),
            "attachments": self.attachments_entry.get(),
        }
        try:
            if self._task is None:
                self._controller.create_work(
                    title=values["title"], description=values["description"],
                    assigned_employee=values["assigned_employee"], department=values["department"],
                    priority=values["priority"], due_date=values["due_date"],
                    estimated_hours=values["estimated_hours"], category=values["category"],
                    start_date=values["start_date"], checklist=values["checklist"],
                    comments=values["comments"], attachments=values["attachments"],
                )
            else:
                self._controller.update_work(task_id=self._task.id, **values)
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return
        self._on_saved()
        self.destroy()

    def _delete(self) -> None:
        if self._task is not None and self._task.id is not None:
            self._controller.delete_work(self._task.id)
            self._on_saved()
            self.destroy()
