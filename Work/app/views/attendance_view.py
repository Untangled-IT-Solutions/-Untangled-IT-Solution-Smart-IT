"""Attendance workspace view."""

import customtkinter as ctk

from app.controllers.attendance_controller import AttendanceController
from app.models.attendance import AttendanceRecord
from app.models.employee import Employee
from app.utils.theme import Theme
from app.utils.timezone import utc_to_local


class AttendanceView(ctk.CTkFrame):
    """Provides clock actions, real-time totals, and a weekly attendance history."""

    def __init__(
        self,
        master: object,
        controller: AttendanceController,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._initial_filters = filters or {}
        self._can_manage = self._controller.can_manage_attendance()
        self._employees = self._controller.get_employees() if self._can_manage else [self._controller.current_employee()]
        self._employees_by_name = {
            employee.full_name: employee for employee in self._employees if employee.id is not None
        }
        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(
            self, text="Attendance", text_color=Theme.TEXT, font=("Segoe UI", 30, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        controls = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        controls.grid(row=1, column=0, columnspan=2, pady=(20, 18), sticky="ew")
        names = list(self._employees_by_name) or ["No employees"]
        controls.grid_columnconfigure(1, weight=1)
        if self._can_manage:
            ctk.CTkLabel(
                controls, text="Employee", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12)
            ).grid(row=0, column=0, padx=(16, 8), pady=14, sticky="w")
            self.employee_menu = ctk.CTkOptionMenu(
                controls, values=names, fg_color=Theme.PANEL_ALT, button_color=Theme.ACCENT,
                button_hover_color=Theme.ACCENT_HOVER, text_color=Theme.TEXT,
                dropdown_text_color=Theme.TEXT, dropdown_fg_color=Theme.PANEL,
                dropdown_hover_color=Theme.PANEL_ALT, command=lambda _value: self.refresh()
            )
            self.employee_menu.set(names[0])
            self.employee_menu.grid(row=0, column=1, padx=(0, 16), pady=14, sticky="ew")
        else:
            self.employee_menu = None
            ctk.CTkLabel(
                controls,
                text=f"Signed in as {names[0]}",
                text_color=Theme.TEXT,
                font=("Segoe UI", 13, "bold"),
            ).grid(row=0, column=0, columnspan=2, padx=16, pady=14, sticky="w")
        self.status_label = ctk.CTkLabel(
            controls, text="", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 13)
        )
        self.status_label.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 14), sticky="w")

        actions = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        actions.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(
            actions, text="Today's Actions", text_color=Theme.TEXT, font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, columnspan=2, padx=18, pady=(18, 14), sticky="w")
        self.clock_in_button = self._action_button(actions, "Clock In", self._clock_in, 1, 0, Theme.SUCCESS)
        self.clock_out_button = self._action_button(actions, "Clock Out", self._clock_out, 1, 1, Theme.DANGER)
        self.start_break_button = self._action_button(actions, "Start Break", self._start_break, 2, 0, Theme.WARNING)
        self.end_break_button = self._action_button(actions, "End Break", self._end_break, 2, 1, Theme.ACCENT)
        self.error_label = ctk.CTkLabel(actions, text="", text_color=Theme.DANGER, font=("Segoe UI", 12))
        self.error_label.grid(row=3, column=0, columnspan=2, padx=18, pady=(10, 0), sticky="w")
        self.total_label = ctk.CTkLabel(
            actions, text="", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 13), justify="left"
        )
        self.total_label.grid(row=4, column=0, columnspan=2, padx=18, pady=(12, 18), sticky="w")

        history = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        history.grid(row=2, column=1, sticky="nsew", padx=(10, 0))
        history.grid_columnconfigure(0, weight=1)
        history.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            history, text="Attendance History", text_color=Theme.TEXT, font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, padx=18, pady=(18, 12), sticky="w")
        self.history_frame = ctk.CTkScrollableFrame(history, fg_color="transparent", corner_radius=0)
        self.history_frame.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self.history_frame.grid_columnconfigure(0, weight=1)

    def _action_button(
        self, master: object, text: str, command: object, row: int, column: int, color: str
    ) -> ctk.CTkButton:
        button = ctk.CTkButton(
            master, text=text, height=40, fg_color=color,
            hover_color=Theme.ACCENT_HOVER if color != Theme.DANGER else Theme.DANGER_HOVER, command=command
        )
        button.grid(row=row, column=column, padx=(18 if column == 0 else 8, 8 if column == 0 else 18), pady=5, sticky="ew")
        return button

    def refresh(self) -> None:
        """Refresh daily state and automatically generated timesheet totals."""
        employee = self._selected_employee()
        if employee is None or employee.id is None:
            return
        record = self._controller.get_today_record(employee.id)
        self.error_label.configure(text="")
        self._render_state(record)
        self._render_timesheet(employee.id)

    def _render_state(self, record: AttendanceRecord | None) -> None:
        if record is None:
            self.status_label.configure(text="Not clocked in today")
            self.total_label.configure(text="Daily Total: 0.00 h\nWeekly Total: 0.00 h\nMonthly Total: 0.00 h")
            self._set_actions("normal", "disabled", "disabled", "disabled")
            return
        live_hours = self._controller.get_live_hours(record)
        state = "On break" if record.is_on_break else ("Clocked in" if record.is_clocked_in else "Clocked out")
        self.status_label.configure(text=f"{state} | Break Time: {record.break_duration_minutes} min")
        employee = self._selected_employee()
        weekly = self._controller.get_weekly_total(employee.id) if employee and employee.id else 0
        monthly = self._controller.get_monthly_total(employee.id) if employee and employee.id else 0
        self.total_label.configure(
            text=f"Daily Total: {live_hours:.2f} h\nWeekly Total: {weekly:.2f} h\nMonthly Total: {monthly:.2f} h"
        )
        if not record.is_clocked_in:
            self._set_actions("disabled", "disabled", "disabled", "disabled")
        elif record.is_on_break:
            self._set_actions("disabled", "normal", "disabled", "normal")
        else:
            self._set_actions("disabled", "normal", "normal", "disabled")

    def _render_timesheet(self, employee_id: int) -> None:
        for child in self.history_frame.winfo_children():
            child.destroy()
        records = self._controller.get_weekly_timesheet(employee_id)
        if not records:
            ctk.CTkLabel(
                self.history_frame, text="No attendance records this week.",
                text_color=Theme.MUTED_TEXT, font=("Segoe UI", 13)
            ).grid(row=0, column=0, sticky="w")
            return
        for row, record in enumerate(records):
            ctk.CTkLabel(
                self.history_frame,
                text=f"{record.work_date}  |  In {self._time(record.clock_in_at)}  |  Out {self._time(record.clock_out_at)}  |  Break {record.break_duration_minutes} min  |  {record.hours_worked:.2f} h",
                text_color=Theme.TEXT, font=("Segoe UI", 12), anchor="w"
            ).grid(row=row, column=0, pady=(0, 10), sticky="ew")
        if self._can_manage:
            self._render_management_summary(start_row=len(records) + 1)

    def _render_management_summary(self, start_row: int) -> None:
        ctk.CTkLabel(
            self.history_frame,
            text="Today - Team Attendance",
            text_color=Theme.TEXT,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=start_row, column=0, pady=(12, 10), sticky="w")
        records = self._controller.get_today_records()
        if not records:
            ctk.CTkLabel(
                self.history_frame,
                text="No team attendance records today.",
                text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 12),
            ).grid(row=start_row + 1, column=0, sticky="w")
            return
        for offset, record in enumerate(records, start=1):
            status = "On break" if record.is_on_break else ("Clocked in" if record.is_clocked_in else "Clocked out")
            ctk.CTkLabel(
                self.history_frame,
                text=(
                    f"{record.employee_name} | {status} | In {self._time(record.clock_in_at)} | "
                    f"Out {self._time(record.clock_out_at)} | Break {record.break_duration_minutes} min | "
                    f"{record.hours_worked:.2f} h | {self._late_status(record)}"
                ),
                text_color=Theme.TEXT,
                font=("Segoe UI", 12),
                anchor="w",
            ).grid(row=start_row + offset, column=0, pady=(0, 8), sticky="ew")

    def _clock_in(self) -> None:
        self._run_action("clock_in")

    def _clock_out(self) -> None:
        self._run_action("clock_out")

    def _start_break(self) -> None:
        self._run_action("start_break")

    def _end_break(self) -> None:
        self._run_action("end_break")

    def _run_action(self, action: str) -> None:
        employee = self._selected_employee()
        if employee is None or employee.id is None:
            return
        try:
            getattr(self._controller, action)(employee.id)
        except (PermissionError, ValueError) as error:
            self.error_label.configure(text=str(error))
            return
        self.refresh()

    def _selected_employee(self) -> Employee | None:
        if self.employee_menu is not None:
            return self._employees_by_name.get(self.employee_menu.get())
        return self._employees[0] if self._employees else None

    def _set_actions(self, clock_in: str, clock_out: str, start_break: str, end_break: str) -> None:
        self.clock_in_button.configure(state=clock_in)
        self.clock_out_button.configure(state=clock_out)
        self.start_break_button.configure(state=start_break)
        self.end_break_button.configure(state=end_break)

    @staticmethod
    def _time(value: str) -> str:
        if not value:
            return "-"
        return utc_to_local(value)[11:]

    @classmethod
    def _late_status(cls, record: AttendanceRecord) -> str:
        if not record.clock_in_at:
            return "No clock-in"
        return "Late" if cls._time(record.clock_in_at) > "08:15:00" else "On time"
