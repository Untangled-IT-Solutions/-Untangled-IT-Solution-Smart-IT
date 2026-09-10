"""Modern split-pane People directory for Untangled Nexus."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from app.controllers.people_controller import PeopleController
from app.models.employee import Employee
from app.utils.theme import Theme
from app.widgets.employee_card import EmployeeCard

if TYPE_CHECKING:
    from app.models.account import UserAccount


class PeopleView(ctk.CTkFrame):
    """Searchable employee directory with presence and profile preview."""

    PRESENCE_COLORS = {
        "online": "#22C55E", "away": "#EAB308",
        "dnd": "#EF4444", "offline": "#6B7280",
    }

    def __init__(
        self,
        master: object,
        controller: PeopleController,
        filters: dict[str, object] | None = None,
        current_account: "UserAccount | None" = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._initial_filters = filters or {}
        self._account = current_account
        self._actor = str(
            getattr(current_account, "full_name", "")
            or getattr(current_account, "username", "") or ""
        )
        self._selected_employee_id: object | None = None
        self._all_employees: list[Employee] = []
        self._visible_employees: list[Employee] = []
        self._cards: dict[object, EmployeeCard] = {}
        self._filter_buttons: dict[str, ctk.CTkButton] = {}
        self._refresh_job = None
        self._live_job = None
        self._quick_filter = ctk.StringVar(value="All")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_header()
        self._build_toolbar()
        self._build_directory()
        self.refresh()
        self._schedule_live_refresh()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            header, text="People", text_color=Theme.TEXT, font=Theme.FONT_TITLE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Find colleagues, see availability and understand who is working on what.",
            text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY,
        ).pack(anchor="w", pady=(3, 0))

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        toolbar.grid(row=1, column=0, pady=(16, 12), sticky="ew")
        toolbar.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(
            toolbar, height=42,
            placeholder_text="Search by name, job title or skills…",
            fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER,
        )
        self.search_entry.grid(row=0, column=0, padx=(14, 10), pady=14, sticky="ew")
        self.search_entry.bind("<KeyRelease>", lambda _event: self._schedule_search())
        button_bar = ctk.CTkFrame(toolbar, fg_color="transparent")
        button_bar.grid(row=0, column=1, padx=(0, 14), pady=14, sticky="e")
        filter_styles = (
            ("All", Theme.INFO, 76),
            ("Currently Active", Theme.SUCCESS, 146),
            ("My Team", Theme.PURPLE, 92),
        )
        for column, (label, color, width) in enumerate(filter_styles):
            button = ctk.CTkButton(
                button_bar, text=label, width=width, height=38,
                fg_color=color, hover_color=Theme.ACCENT_HOVER,
                text_color="#FFFFFF", font=("Segoe UI", 12, "bold"),
                border_color="#FFFFFF",
                command=lambda value=label: self._set_quick_filter(value),
            )
            button.grid(row=0, column=column, padx=(0 if column == 0 else 6, 0))
            self._filter_buttons[label] = button
        self._update_filter_buttons()

    def _set_quick_filter(self, value: str) -> None:
        self._quick_filter.set(value)
        self._update_filter_buttons()
        self._render_directory()

    def _update_filter_buttons(self) -> None:
        selected = self._quick_filter.get()
        for label, button in self._filter_buttons.items():
            button.configure(border_width=3 if label == selected else 0)

    def _build_directory(self) -> None:
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.grid(row=2, column=0, sticky="nsew")
        split.grid_columnconfigure(0, weight=3, minsize=470)
        split.grid_columnconfigure(1, weight=2, minsize=370)
        split.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            split, text="Team Directory", text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.result_label = ctk.CTkLabel(
            split, text="", text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL,
        )
        self.result_label.grid(row=0, column=0, padx=(170, 0), sticky="w")
        ctk.CTkLabel(
            split, text="Preview Profile", text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=1, padx=(16, 0), sticky="w", pady=(0, 8))
        self._cards_frame = ctk.CTkScrollableFrame(
            split, fg_color="transparent", corner_radius=0,
        )
        self._cards_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self._cards_frame.grid_columnconfigure(0, weight=1)
        self._profile_frame = ctk.CTkScrollableFrame(
            split, fg_color=Theme.PANEL, border_color=Theme.BORDER,
            border_width=1, corner_radius=Theme.RADIUS,
        )
        self._profile_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        self._profile_frame.grid_columnconfigure(0, weight=1)

    def refresh(self) -> None:
        """Reload live employee records while preserving selection."""
        try:
            self._all_employees = self._controller.get_employees(
                self.search_entry.get().strip(), "All", "All", "All"
            )
        except Exception as exc:
            self._all_employees = []
            self._render_error(str(exc))
            return
        self._render_directory()

    def _schedule_search(self) -> None:
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(250, self.refresh)

    def _schedule_live_refresh(self) -> None:
        self._live_job = self.after(30000, self._live_refresh)

    def _live_refresh(self) -> None:
        self._live_job = None
        if not self.winfo_exists():
            return
        self.refresh()
        self._schedule_live_refresh()

    def _render_directory(self) -> None:
        employees = list(self._all_employees)
        selected_filter = self._quick_filter.get()
        if selected_filter == "Currently Active":
            employees = [employee for employee in employees if employee.presence == "online"]
        elif selected_filter == "My Team":
            employees = self._my_team(employees)
        self._visible_employees = employees
        self.result_label.configure(
            text=f"{len(employees)} {'person' if len(employees) == 1 else 'people'}"
        )
        for child in self._cards_frame.winfo_children():
            child.destroy()
        self._cards = {}
        if not employees:
            ctk.CTkLabel(
                self._cards_frame,
                text="No employees match this search or filter.",
                text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY,
            ).grid(row=0, column=0, padx=16, pady=36, sticky="w")
            self._render_empty_profile()
            return
        if not any(employee.id == self._selected_employee_id for employee in employees):
            self._selected_employee_id = employees[0].id
        for row, employee in enumerate(employees):
            card = EmployeeCard(
                self._cards_frame, employee, self._show_profile,
                selected=employee.id == self._selected_employee_id,
            )
            card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            if employee.id is not None:
                self._cards[employee.id] = card
        selected = next(
            (employee for employee in employees if employee.id == self._selected_employee_id),
            employees[0],
        )
        self._render_profile(selected)

    def _my_team(self, employees: list[Employee]) -> list[Employee]:
        if not self._actor:
            return employees
        current = next(
            (employee for employee in employees if employee.full_name.casefold() == self._actor.casefold()),
            None,
        )
        if current is None:
            try:
                current = self._controller.get_employee_by_name(self._actor)
            except Exception:
                current = None
        if current is None:
            return employees
        team = (current.team or current.department).strip().casefold()
        return [
            employee for employee in employees
            if employee.full_name.casefold() == self._actor.casefold()
            or (team and (employee.team or employee.department).strip().casefold() == team)
            or employee.reports_to.strip().casefold() == self._actor.casefold()
        ]

    def _show_profile(self, employee_id: object) -> None:
        previous = self._cards.get(self._selected_employee_id)
        if previous:
            previous.set_selected(False)
        self._selected_employee_id = employee_id
        current_card = self._cards.get(employee_id)
        if current_card:
            current_card.set_selected(True)
        employee = next(
            (person for person in self._visible_employees if person.id == employee_id), None
        )
        if employee is None:
            employee = self._controller.get_employee(employee_id)
        if employee is not None:
            self.after_idle(lambda: self._render_profile(employee))

    def _render_profile(self, employee: Employee) -> None:
        self._clear_profile()
        try:
            tasks = self._controller.get_current_tasks(employee.full_name)
        except Exception:
            tasks = []
        header = ctk.CTkFrame(self._profile_frame, fg_color="transparent")
        header.grid(row=0, column=0, padx=18, pady=(18, 12), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        avatar = ctk.CTkFrame(header, width=72, height=72, fg_color="transparent")
        avatar.grid(row=0, column=0, rowspan=4, padx=(0, 12), sticky="n")
        avatar.grid_propagate(False)
        initials = "".join(part[:1] for part in employee.full_name.split()[:2]).upper() or "?"
        ctk.CTkLabel(
            avatar, text=initials, width=64, height=64, corner_radius=32,
            fg_color=Theme.PANEL_ALT, text_color=Theme.TEXT,
            font=("Segoe UI", 19, "bold"),
        ).place(x=0, y=0)
        ctk.CTkLabel(
            avatar, text="●", width=21, height=21, corner_radius=10,
            fg_color=Theme.PANEL,
            text_color=self.PRESENCE_COLORS.get(employee.presence, "#6B7280"),
            font=("Segoe UI", 18, "bold"),
        ).place(x=47, y=46)
        ctk.CTkLabel(
            header, text=employee.full_name, text_color=Theme.TEXT,
            font=("Segoe UI", 21, "bold"), anchor="w", wraplength=280,
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            header, text=f"@{employee.username.lstrip('@')}",
            text_color=Theme.ACCENT, font=("Segoe UI", 12, "bold"),
        ).grid(row=1, column=1, sticky="w")
        ctk.CTkLabel(
            header, text=employee.position or "Team Member",
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12),
        ).grid(row=2, column=1, sticky="w", pady=(3, 0))
        ctk.CTkLabel(
            header, text=employee.team or employee.department or "General",
            fg_color=Theme.PANEL_ALT, corner_radius=9, padx=9, pady=3,
            text_color=Theme.TEXT, font=("Segoe UI", 10, "bold"),
        ).grid(row=3, column=1, sticky="w", pady=(6, 0))

        self._contact_section(employee, 1)
        employment = (
            f"Employee number: {employee.employee_number or 'Not captured'}\n"
            f"Job title: {employee.position or 'Not captured'}\n"
            f"Department: {employee.department or 'Not captured'}\n"
            f"Team: {employee.team or 'Not captured'}\n"
            f"Role: {employee.role or 'Not captured'}\n"
            f"Employment type: {employee.employment_type or 'Not captured'}\n"
            f"Date joined: {employee.date_joined or 'Not captured'}\n"
            f"Account status: {employee.status or 'Not captured'}\n"
            f"Attendance: {'Clocked In' if employee.clocked_in else 'Clocked Out'}"
        )
        self._text_section("Employment Details", employment, 2, "Complete employee record")
        work = "\n".join(tasks) if tasks else (employee.current_task or "No active work recorded")
        self._text_section("Current Work", work, 3, "Active assignments and tickets")
        self._skills_section(employee, 4)
        self._org_section(employee, 5)
        additional = (
            f"Permissions: {employee.permissions or 'Role-managed'}\n"
            f"Training progress: {employee.training_progress:.0f}%\n"
            f"Performance score: {employee.performance_score:.0f}%\n"
            f"Notes: {employee.notes or 'No notes captured'}"
        )
        self._text_section("Additional Information", additional, 6, "Other stored profile information")

    def _contact_section(self, employee: Employee, row: int) -> None:
        panel = self._section_panel("Contact Details", row, "How to reach this colleague")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel, text=employee.email or "Email not captured",
            text_color=Theme.TEXT, font=("Segoe UI", 12), anchor="w",
        ).grid(row=2, column=0, padx=14, pady=(8, 3), sticky="ew")
        copy_button = ctk.CTkButton(
            panel, text="Copy", width=66, height=28,
            fg_color=Theme.INFO, command=lambda: self._copy_email(employee.email, copy_button),
        )
        copy_button.grid(row=2, column=1, padx=14, pady=(8, 3), sticky="e")
        ctk.CTkLabel(
            panel,
            text=(
                f"Phone: {employee.phone or 'Not captured'}\n"
                f"Slack: {employee.slack_handle or 'Not captured'}\n"
                f"Time zone: {employee.timezone or 'Africa/Johannesburg (SAST)'}"
            ),
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 11),
            justify="left", anchor="w",
        ).grid(row=3, column=0, columnspan=2, padx=14, pady=(3, 13), sticky="ew")

    def _copy_email(self, email: str, button: ctk.CTkButton) -> None:
        if not email:
            return
        self.clipboard_clear()
        self.clipboard_append(email)
        button.configure(text="Copied", fg_color=Theme.SUCCESS)
        self.after(1400, lambda: button.winfo_exists() and button.configure(text="Copy", fg_color=Theme.INFO))

    def _text_section(self, title: str, body: str, row: int, subtitle: str = "") -> None:
        panel = self._section_panel(title, row, subtitle)
        ctk.CTkLabel(
            panel, text=body, text_color=Theme.TEXT, font=("Segoe UI", 12),
            justify="left", anchor="w", wraplength=390,
        ).grid(row=2, column=0, padx=14, pady=(8, 14), sticky="ew")

    def _skills_section(self, employee: Employee, row: int) -> None:
        panel = self._section_panel("Skills", row, "Areas of experience")
        tags = [tag.strip() for tag in (employee.skills or "").replace(";", ",").split(",") if tag.strip()]
        if not tags:
            tags = ["Profile skills not captured"]
        tag_frame = ctk.CTkFrame(panel, fg_color="transparent")
        tag_frame.grid(row=2, column=0, padx=11, pady=(7, 12), sticky="ew")
        for index, tag in enumerate(tags):
            ctk.CTkLabel(
                tag_frame, text=tag, fg_color=Theme.PANEL_ALT,
                text_color=Theme.TEXT, corner_radius=10, padx=9, pady=4,
                font=("Segoe UI", 10, "bold"),
            ).grid(row=index // 3, column=index % 3, padx=3, pady=3, sticky="w")

    def _org_section(self, employee: Employee, row: int) -> None:
        reports = [
            person.full_name for person in self._all_employees
            if person.reports_to.strip().casefold() == employee.full_name.strip().casefold()
        ]
        manager = employee.reports_to or "Not assigned"
        report_text = ", ".join(reports) if reports else "No direct reports"
        self._text_section(
            "Organisation",
            f"Direct manager\n{manager}\n\nMentor\n{employee.mentor or 'Not assigned'}\n\nDirect reports\n{report_text}",
            row, "Reporting-line snapshot",
        )

    def _section_panel(self, title: str, row: int, subtitle: str = "") -> ctk.CTkFrame:
        panel = ctk.CTkFrame(
            self._profile_frame, fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER, border_width=1, corner_radius=Theme.RADIUS,
        )
        panel.grid(row=row, column=0, padx=14, pady=(0, 10), sticky="ew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel, text=title, text_color=Theme.TEXT,
            font=("Segoe UI", 13, "bold"), anchor="w",
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 0), sticky="ew")
        if subtitle:
            ctk.CTkLabel(
                panel, text=subtitle, text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 10), anchor="w",
            ).grid(row=1, column=0, columnspan=2, padx=14, pady=(1, 0), sticky="ew")
        return panel

    def _render_empty_profile(self) -> None:
        self._clear_profile()
        ctk.CTkLabel(
            self._profile_frame, text="Select an employee to preview their profile.",
            text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY, wraplength=300,
        ).grid(row=0, column=0, padx=22, pady=34, sticky="w")

    def _render_error(self, message: str) -> None:
        for child in self._cards_frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self._cards_frame,
            text=f"The employee directory could not be loaded.\n{message}",
            text_color=Theme.DANGER, font=Theme.FONT_BODY,
            justify="left", wraplength=500,
        ).grid(row=0, column=0, padx=18, pady=30, sticky="w")
        self._render_empty_profile()

    def _clear_profile(self) -> None:
        for child in self._profile_frame.winfo_children():
            child.destroy()

    def destroy(self) -> None:
        for job in (self._refresh_job, self._live_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        super().destroy()
