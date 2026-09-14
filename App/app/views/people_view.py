"""People directory – thin view over PeopleController + BaseWorkspaceView."""

from __future__ import annotations

from typing import Any, Optional

import customtkinter as ctk

from app.controllers.people_controller import PeopleController
from app.models.employee import Employee
from app.ui.base_workspace_view import BaseWorkspaceView
from app.utils.theme import Theme
from app.widgets.employee_card import EmployeeCard
from app.utils.debounce import Debouncer


class PeopleView(BaseWorkspaceView):
    """Employee directory + profile panel. Network only via controller in load_data()."""

    PAGE_TITLE = "People"
    PAGE_SUBTITLE = "Employee directory and profiles"

    def __init__(
        self,
        master: object,
        controller: PeopleController,
        filters: dict[str, object] | None = None,
    ) -> None:
        self._controller = controller
        self._initial_filters = filters or {}
        self._cards_frame: Optional[ctk.CTkScrollableFrame] = None
        self._profile_frame: Optional[ctk.CTkScrollableFrame] = None
        self._selected_employee_id: Any = None
        super().__init__(master)
        self._apply_initial_filters()
        self.refresh()

    def build(self) -> None:
        body = self._body
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        filters = ctk.CTkFrame(body, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        filters.grid(row=0, column=0, columnspan=2, pady=(0, 14), sticky="ew")
        filters.grid_columnconfigure(0, weight=2)
        filters.grid_columnconfigure((1, 2, 3), weight=1)

        self.search_entry = ctk.CTkEntry(
            filters,
            height=38,
            placeholder_text="Search employees",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
        )
        self.search_entry.grid(row=0, column=0, padx=14, pady=14, sticky="ew")
        self._search_debouncer = Debouncer(self, delay_ms=280)
        self.search_entry.bind(
            "<KeyRelease>",
            lambda _e: self._search_debouncer.call(lambda: self.refresh(force=True)),
        )

        self.department_filter = self._filter_menu(filters, self._controller.get_departments(), 1)
        self.role_filter = self._filter_menu(filters, self._controller.get_roles(), 2)
        self.status_filter = self._filter_menu(filters, self._controller.get_statuses(), 3)

        self._cards_frame = ctk.CTkScrollableFrame(body, fg_color="transparent", corner_radius=0)
        self._cards_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 18))
        self._cards_frame.grid_columnconfigure(0, weight=1)

        self._profile_frame = ctk.CTkScrollableFrame(
            body, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS
        )
        self._profile_frame.grid(row=1, column=1, sticky="nsew")
        self._profile_frame.grid_columnconfigure(0, weight=1)
        self._render_empty_profile()

    def cache_key(self) -> str | None:
        try:
            return (
                f"people:{self.search_entry.get()}|"
                f"{self.department_filter.get()}|"
                f"{self.role_filter.get()}|"
                f"{self.status_filter.get()}"
            )
        except Exception:
            return "people:default"

    def load_data(self) -> list[Employee]:
        return self._controller.get_employees(
            self.search_entry.get(),
            self.department_filter.get(),
            self.role_filter.get(),
            self.status_filter.get(),
        ) or []

    def apply_data(self, employees: list[Employee]) -> None:
        if self._cards_frame is None:
            return
        for child in self._cards_frame.winfo_children():
            child.destroy()
        employees = employees or []
        for row, employee in enumerate(employees):
            EmployeeCard(self._cards_frame, employee, self._show_profile).grid(
                row=row, column=0, sticky="ew", pady=(0, 12)
            )
        selected = next(
            (e for e in employees if e.id == self._selected_employee_id),
            employees[0] if employees else None,
        )
        if selected is None:
            self._render_empty_profile()
        else:
            self._selected_employee_id = selected.id
            self._render_profile(selected)

    def on_load_error(self, error: Exception) -> None:
        super().on_load_error(error)
        if self._cards_frame is not None:
            for child in self._cards_frame.winfo_children():
                child.destroy()
        self._render_empty_profile()

    def _apply_initial_filters(self) -> None:
        dept = self._initial_filters.get("department")
        if isinstance(dept, str) and dept in self.department_filter.cget("values"):
            self.department_filter.set(dept)

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

    def _show_profile(self, employee_id: Any) -> None:
        self._selected_employee_id = employee_id
        employee = self._controller.get_employee(employee_id)
        if employee is None:
            self._render_empty_profile()
        else:
            self._render_profile(employee)

    def _render_empty_profile(self) -> None:
        self._clear_profile()
        if self._profile_frame is None:
            return
        ctk.CTkLabel(
            self._profile_frame,
            text="Select an employee",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 14),
        ).grid(row=0, column=0, padx=20, pady=40)

    def _render_profile(self, employee: Employee) -> None:
        self._clear_profile()
        if self._profile_frame is None:
            return
        tasks = self._controller.get_current_tasks(employee.full_name) or []

        header = ctk.CTkFrame(self._profile_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header,
            text=(employee.full_name[:1] or "?").upper(),
            width=48,
            height=48,
            corner_radius=24,
            fg_color=Theme.ACCENT,
            text_color="#FFFFFF",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, rowspan=2, padx=(0, 12), sticky="nw")
        ctk.CTkLabel(
            header,
            text=employee.full_name,
            text_color=Theme.TEXT,
            font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=1, sticky="w")
        clock_label = "Clocked In" if employee.clocked_in else "Clocked Out"
        ctk.CTkLabel(
            header,
            text=f"{employee.status} | {clock_label}",
            text_color=Theme.SUCCESS if employee.status == "Active" else Theme.WARNING,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=1, column=1, pady=(4, 0), sticky="w")

        sections = (
            ("Personal Information", f"Employee Number: {employee.employee_number}\nEmail: {employee.email}\nPhone: {employee.phone or 'Not captured'}"),
            ("Employment Information", f"{employee.position}\n{employee.department}\n{employee.employment_type}\nJoined: {employee.date_joined or 'Not captured'}"),
            ("Reporting Structure", f"Reports To: {employee.reports_to or 'Not assigned'}\nMentor: {employee.mentor or 'Not assigned'}"),
            ("Skills", employee.skills or "No skills captured"),
            ("Permissions", employee.permissions or "Permissions are role-managed"),
            ("Training Progress", f"{employee.training_progress:.0f}% complete"),
            ("Performance Score", f"{employee.performance_score:.0f}%"),
            ("Current Status", f"{employee.status} | {clock_label}"),
            ("Current Task", "\n".join(tasks) if tasks else employee.current_task),
            ("Notes", employee.notes or "No notes captured"),
        )
        for index, (title, body) in enumerate(sections, start=1):
            self._profile_section(title, body, index)

    def _profile_section(self, title: str, body: str, row: int) -> None:
        if self._profile_frame is None:
            return
        ctk.CTkLabel(
            self._profile_frame,
            text=title,
            text_color=Theme.TEXT,
            font=("Segoe UI", 13, "bold"),
        ).grid(row=row * 2, column=0, padx=20, pady=(0 if row == 1 else 12, 2), sticky="w")
        ctk.CTkLabel(
            self._profile_frame,
            text=body,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12),
            justify="left",
            wraplength=310,
        ).grid(row=(row * 2) + 1, column=0, padx=20, sticky="w")

    def _clear_profile(self) -> None:
        if self._profile_frame is not None:
            for child in self._profile_frame.winfo_children():
                child.destroy()
