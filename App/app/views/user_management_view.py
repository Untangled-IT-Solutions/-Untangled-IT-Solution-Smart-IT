"""
Responsive MongoDB User Management view.

This view manages real employee login accounts through the controller.

MongoDB relationship:

    employees
        employee_id
        first_name
        surname
        full_name
        email
        department
        position

    users
        employee_id
        username
        password_hash
        role
        status
        last_login_at

This file contains UI only.
MongoDB operations are delegated to the controller/service layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import customtkinter as ctk

from app.utils.theme import Theme


class UserManagementView(ctk.CTkFrame):
    """Responsive MongoDB employee account and credential management screen."""

    ROLES = (
        "Director",
        "Business Lead",
        "Operations Manager",
        "Staff",
        "Intern",
    )

    def __init__(self, master: object, controller: object) -> None:
        super().__init__(
            master,
            fg_color=Theme.BG,
            corner_radius=0,
        )

        self._controller = controller

        # Keyed by the application's MongoDB employee_id.
        #
        # IMPORTANT:
        # Do not use MongoDB's ObjectId (_id) as the application
        # employee relationship.
        self._employees: dict[str, dict[str, Any]] = {}

        self._resize_job: str | None = None
        self._compact: bool | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=Theme.PANEL_ALT,
            scrollbar_button_hover_color=Theme.BORDER,
        )
        self.content.grid(
            row=0,
            column=0,
            sticky="nsew",
        )
        self.content.grid_columnconfigure(0, weight=1)

        self._build_layout()

        self.bind(
            "<Configure>",
            self._schedule_resize,
            add="+",
        )

        self.after_idle(self._apply_responsive_layout)

        self._refresh_all()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self._build_header()
        self._build_form()
        self._build_statistics()
        self._build_accounts()

    def _build_header(self) -> None:
        self.header = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )
        self.header.grid(
            row=0,
            column=0,
            padx=28,
            pady=(22, 0),
            sticky="ew",
        )
        self.header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header,
            text="User Management",
            text_color=Theme.TEXT,
            font=Theme.FONT_TITLE,
        )
        self.title_label.grid(
            row=0,
            column=0,
            sticky="w",
        )

        ctk.CTkLabel(
            self.header,
            text=(
                "Manage real employee login credentials, passwords, "
                "roles, and account status."
            ),
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).grid(
            row=1,
            column=0,
            pady=(2, 0),
            sticky="w",
        )

        ctk.CTkButton(
            self.header,
            text="Refresh",
            width=100,
            height=34,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._refresh_all,
        ).grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="e",
        )

    def _build_form(self) -> None:
        self.form = ctk.CTkFrame(
            self.content,
            fg_color=Theme.PANEL,
            corner_radius=Theme.RADIUS,
        )
        self.form.grid(
            row=1,
            column=0,
            padx=28,
            pady=(18, 0),
            sticky="ew",
        )
        self.form.grid_columnconfigure(
            (0, 1),
            weight=1,
        )

        ctk.CTkLabel(
            self.form,
            text="Employee login credentials",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            padx=18,
            pady=(16, 4),
            sticky="w",
        )

        ctk.CTkLabel(
            self.form,
            text=(
                "Select a real employee from MongoDB. "
                "Existing accounts can be updated."
            ),
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 14),
            sticky="w",
        )

        self.employee_label = self._label("Employee")
        self.username_label = self._label("Username")
        self.password_label = self._label("New Password")
        self.role_label = self._label("Role")

        self.employee_menu = ctk.CTkOptionMenu(
            self.form,
            values=["Select Employee..."],
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
            command=self._employee_selected,
        )

        self.username_entry = ctk.CTkEntry(
            self.form,
            height=40,
            placeholder_text="Auto-generated from employee name",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
        )

        self.password_entry = ctk.CTkEntry(
            self.form,
            height=40,
            placeholder_text="Enter a new password",
            show="*",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
        )
        self.password_entry.bind(
            "<KeyRelease>",
            self._update_password_strength,
        )

        self.role_menu = ctk.CTkOptionMenu(
            self.form,
            values=list(self.ROLES),
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
        )
        self.role_menu.set("Staff")

        self.password_hint = ctk.CTkLabel(
            self.form,
            text=(
                "Use 8+ characters with upper, lower, "
                "number, and symbol."
            ),
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        )

        self.show_password = ctk.CTkCheckBox(
            self.form,
            text="Show password",
            text_color=Theme.TEXT,
            command=self._toggle_password,
        )

        self.active_checkbox = ctk.CTkCheckBox(
            self.form,
            text="Activate account",
            text_color=Theme.TEXT,
        )
        self.active_checkbox.select()

        self.actions = ctk.CTkFrame(
            self.form,
            fg_color="transparent",
        )
        self.actions.grid_columnconfigure(
            (0, 1),
            weight=1,
        )

        self.save_button = ctk.CTkButton(
            self.actions,
            text="Save credentials",
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._save_credentials,
        )
        self.save_button.grid(
            row=0,
            column=0,
            padx=(0, 5),
            sticky="ew",
        )

        self.generate_button = ctk.CTkButton(
            self.actions,
            text="Generate password",
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            command=self._generate_credentials,
        )
        self.generate_button.grid(
            row=0,
            column=1,
            padx=(5, 0),
            sticky="ew",
        )

        self.status_label = ctk.CTkLabel(
            self.form,
            text="",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
            justify="left",
            wraplength=720,
        )

    def _build_statistics(self) -> None:
        self.stats = ctk.CTkFrame(
            self.content,
            fg_color=Theme.PANEL,
            corner_radius=Theme.RADIUS,
        )
        self.stats.grid(
            row=2,
            column=0,
            padx=28,
            pady=(16, 0),
            sticky="ew",
        )

        ctk.CTkLabel(
            self.stats,
            text="Account overview",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(
            row=0,
            column=0,
            columnspan=4,
            padx=18,
            pady=(14, 6),
            sticky="w",
        )

        self.stat_labels: dict[str, ctk.CTkLabel] = {}

        statistics = (
            ("total_users", "Total accounts"),
            ("active_users", "Active"),
            ("inactive_users", "Inactive"),
            ("last_login", "Last login"),
        )

        for column, (key, title) in enumerate(statistics):
            self.stats.grid_columnconfigure(
                column,
                weight=1,
            )

            item = ctk.CTkFrame(
                self.stats,
                fg_color="transparent",
            )
            item.grid(
                row=1,
                column=column,
                padx=18,
                pady=(2, 14),
                sticky="ew",
            )

            ctk.CTkLabel(
                item,
                text=title,
                text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_SMALL,
            ).pack(anchor="w")

            value = ctk.CTkLabel(
                item,
                text="-",
                text_color=Theme.TEXT,
                font=("Segoe UI", 18, "bold"),
            )
            value.pack(anchor="w")

            self.stat_labels[key] = value

    def _build_accounts(self) -> None:
        self.accounts = ctk.CTkFrame(
            self.content,
            fg_color=Theme.PANEL,
            corner_radius=Theme.RADIUS,
        )
        self.accounts.grid(
            row=3,
            column=0,
            padx=28,
            pady=(16, 28),
            sticky="ew",
        )
        self.accounts.grid_columnconfigure(
            0,
            weight=1,
        )

        header = ctk.CTkFrame(
            self.accounts,
            fg_color="transparent",
        )
        header.grid(
            row=0,
            column=0,
            padx=18,
            pady=(14, 8),
            sticky="ew",
        )
        header.grid_columnconfigure(
            1,
            weight=1,
        )

        ctk.CTkLabel(
            header,
            text="User accounts",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.search_entry = ctk.CTkEntry(
            header,
            height=34,
            placeholder_text="Search users...",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
        )
        self.search_entry.grid(
            row=0,
            column=1,
            padx=(16, 8),
            sticky="ew",
        )
        self.search_entry.bind(
            "<KeyRelease>",
            lambda _event: self._refresh_users(),
        )

        self.filter_menu = ctk.CTkOptionMenu(
            header,
            values=[
                "All Users",
                "Active Only",
                "Inactive Only",
            ],
            width=130,
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            command=lambda _value: self._refresh_users(),
        )
        self.filter_menu.set("All Users")
        self.filter_menu.grid(
            row=0,
            column=2,
            sticky="e",
        )

        self.user_list = ctk.CTkScrollableFrame(
            self.accounts,
            height=280,
            fg_color="transparent",
            scrollbar_button_color=Theme.PANEL_ALT,
            scrollbar_button_hover_color=Theme.BORDER,
        )
        self.user_list.grid(
            row=1,
            column=0,
            padx=10,
            pady=(0, 12),
            sticky="ew",
        )
        self.user_list.grid_columnconfigure(
            0,
            weight=1,
        )

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        self._refresh_employees()
        self._refresh_statistics()
        self._refresh_users()

    def _refresh_employees(self) -> None:
        """
        Load real employees from MongoDB through the controller.

        The controller should return employee dictionaries containing
        at minimum:

            employee_id
            full_name

        Optional:

            first_name
            surname
            department
            position
            email
            has_account
            username
            role
            status
        """
        try:
            employees = self._controller.get_employees_without_accounts()

            self._employees.clear()

            values = ["Select Employee..."]

            for employee in employees:
                employee_id = self._get_employee_id(employee)

                if employee_id is None:
                    continue

                employee_id = str(employee_id)

                self._employees[employee_id] = employee

                full_name = self._employee_name(employee)
                position = str(
                    employee.get("position")
                    or employee.get("job_title")
                    or "Employee"
                )

                has_account = bool(
                    employee.get("has_account")
                    or employee.get("user_id")
                    or employee.get("username")
                )

                state = (
                    "Configured"
                    if has_account
                    else "Needs setup"
                )

                values.append(
                    f"{employee_id}: "
                    f"{full_name} "
                    f"({position}) - {state}"
                )

            self.employee_menu.configure(
                values=values,
            )

            self.employee_menu.set(
                values[0],
            )

        except Exception as error:
            self._message(
                f"Could not load employees: {error}",
                Theme.DANGER,
            )

    def _refresh_statistics(self) -> None:
        try:
            stats = self._controller.get_user_statistics()

            self.stat_labels["total_users"].configure(
                text=str(
                    stats.get(
                        "total_users",
                        0,
                    )
                )
            )

            self.stat_labels["active_users"].configure(
                text=str(
                    stats.get(
                        "active_users",
                        0,
                    )
                )
            )

            self.stat_labels["inactive_users"].configure(
                text=str(
                    stats.get(
                        "inactive_users",
                        0,
                    )
                )
            )

            self.stat_labels["last_login"].configure(
                text=self._display_date(
                    stats.get("last_login")
                )
            )

        except Exception as error:
            self._message(
                f"Could not load statistics: {error}",
                Theme.DANGER,
            )

    def _refresh_users(self) -> None:
        for widget in self.user_list.winfo_children():
            widget.destroy()

        try:
            mode = self.filter_menu.get()

            users = self._controller.get_all_users(
                include_inactive=mode != "Active Only",
            )

            if mode == "Inactive Only":
                users = [
                    user
                    for user in users
                    if str(
                        user.get("status", "")
                    ).lower()
                    != "active"
                ]

            search = (
                self.search_entry
                .get()
                .lower()
                .strip()
            )

            if search:
                users = [
                    user
                    for user in users
                    if (
                        search
                        in str(
                            user.get(
                                "username",
                                "",
                            )
                        ).lower()
                    )
                    or (
                        search
                        in str(
                            user.get(
                                "full_name",
                                "",
                            )
                        ).lower()
                    )
                    or (
                        search
                        in str(
                            user.get(
                                "surname",
                                "",
                            )
                        ).lower()
                    )
                    or (
                        search
                        in str(
                            user.get(
                                "department",
                                "",
                            )
                        ).lower()
                    )
                    or (
                        search
                        in str(
                            user.get(
                                "role",
                                "",
                            )
                        ).lower()
                    )
                ]

            if not users:
                empty = ctk.CTkFrame(
                    self.user_list,
                    fg_color=Theme.PANEL_ALT,
                    corner_radius=Theme.RADIUS,
                )
                empty.pack(
                    fill="x",
                    padx=4,
                    pady=10,
                )

                ctk.CTkLabel(
                    empty,
                    text="No accounts found",
                    text_color=Theme.TEXT,
                    font=Theme.FONT_HEADING,
                ).pack(
                    pady=(18, 3)
                )

                ctk.CTkLabel(
                    empty,
                    text=(
                        "No user accounts match the "
                        "current search or filter."
                    ),
                    text_color=Theme.MUTED_TEXT,
                    font=Theme.FONT_SMALL,
                ).pack(
                    pady=(0, 18)
                )

                return

            for user in users:
                self._user_card(user)

        except Exception as error:
            self._message(
                f"Could not load user accounts: {error}",
                Theme.DANGER,
            )

    # ------------------------------------------------------------------
    # User cards
    # ------------------------------------------------------------------

    def _user_card(
        self,
        user: dict[str, Any],
    ) -> None:
        status = str(
            user.get(
                "status",
                "active",
            )
        ).lower()

        active = status == "active"

        user_id = self._mongo_user_id(user)

        username = str(
            user.get(
                "username",
                "Unknown",
            )
            or "Unknown"
        )

        full_name = self._user_name(user)

        role = str(
            user.get(
                "role",
                "Staff",
            )
            or "Staff"
        )

        department = str(
            user.get(
                "department",
                "No department",
            )
            or "No department"
        )

        employee_id = user.get(
            "employee_id"
        )

        card = ctk.CTkFrame(
            self.user_list,
            fg_color=Theme.PANEL_ALT,
            corner_radius=Theme.RADIUS,
        )
        card.pack(
            fill="x",
            padx=4,
            pady=5,
        )

        card.grid_columnconfigure(
            0,
            weight=1,
        )

        heading = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        heading.grid(
            row=0,
            column=0,
            padx=14,
            pady=(12, 4),
            sticky="ew",
        )
        heading.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkLabel(
            heading,
            text=f"{username}  —  {full_name}",
            text_color=Theme.TEXT,
            font=("Segoe UI", 14, "bold"),
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )

        ctk.CTkLabel(
            heading,
            text="ACTIVE" if active else "INACTIVE",
            fg_color=(
                Theme.SUCCESS
                if active
                else Theme.DANGER
            ),
            text_color="#FFFFFF",
            corner_radius=10,
            padx=9,
            pady=3,
            font=Theme.FONT_SMALL,
        ).grid(
            row=0,
            column=1,
            sticky="e",
        )

        details = (
            f"{role}  |  "
            f"{department}  |  "
            f"Employee ID: {employee_id or '—'}  |  "
            f"Last login: "
            f"{self._display_date(user.get('last_login_at'))}"
        )

        ctk.CTkLabel(
            card,
            text=details,
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
            justify="left",
            wraplength=800,
        ).grid(
            row=1,
            column=0,
            padx=14,
            pady=(0, 8),
            sticky="w",
        )

        actions = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )
        actions.grid(
            row=2,
            column=0,
            padx=14,
            pady=(0, 12),
            sticky="ew",
        )

        ctk.CTkButton(
            actions,
            text="Reset password",
            width=125,
            height=30,
            fg_color=Theme.WARNING,
            hover_color=Theme.WARNING,
            command=lambda: self._reset_password(
                user_id,
                username,
            ),
        ).pack(
            side="left",
            padx=(0, 6),
        )

        ctk.CTkButton(
            actions,
            text=(
                "Deactivate"
                if active
                else "Activate"
            ),
            width=105,
            height=30,
            fg_color=(
                Theme.DANGER
                if active
                else Theme.SUCCESS
            ),
            hover_color=(
                Theme.DANGER_HOVER
                if active
                else Theme.SUCCESS_HOVER
            ),
            command=lambda: self._change_status(
                user_id,
                not active,
            ),
        ).pack(
            side="left",
            padx=6,
        )

        ctk.CTkButton(
            actions,
            text="Delete",
            width=70,
            height=30,
            fg_color=Theme.PANEL,
            hover_color=Theme.DANGER,
            text_color=Theme.DANGER,
            command=lambda: self._delete_user(
                user_id,
                username,
            ),
        ).pack(
            side="right",
        )

    # ------------------------------------------------------------------
    # Employee selection
    # ------------------------------------------------------------------

    def _employee_selected(
        self,
        selection: str,
    ) -> None:
        if selection.startswith(
            "Select Employee"
        ):
            return

        employee_id = (
            selection
            .split(":", 1)[0]
            .strip()
        )

        employee = self._employees.get(
            employee_id
        )

        if not employee:
            return

        # Clear previous form state.
        self.username_entry.delete(
            0,
            "end",
        )

        self.password_entry.delete(
            0,
            "end",
        )

        self._update_password_strength()

        # Fill the employee's existing username if
        # the controller supplied one.
        existing_username = str(
            employee.get(
                "username",
                "",
            )
            or ""
        ).strip()

        if existing_username:
            self.username_entry.insert(
                0,
                existing_username,
            )
        else:
            self.username_entry.insert(
                0,
                self._generate_username(
                    employee
                ),
            )

        existing_role = str(
            employee.get(
                "role",
                "",
            )
            or ""
        )

        if existing_role in self.ROLES:
            self.role_menu.set(
                existing_role
            )
        else:
            self.role_menu.set(
                "Staff"
            )

        existing_status = str(
            employee.get(
                "status",
                "active",
            )
            or "active"
        ).lower()

        if existing_status == "active":
            self.active_checkbox.select()
        else:
            self.active_checkbox.deselect()

        if employee.get("has_account"):
            self.save_button.configure(
                text="Update credentials"
            )
        else:
            self.save_button.configure(
                text="Save credentials"
            )

    # ------------------------------------------------------------------
    # Save / generate / reset
    # ------------------------------------------------------------------

    def _save_credentials(self) -> None:
        """
        Create or update the MongoDB user account.

        The controller/service is responsible for:
            - locating users by employee_id
            - hashing the password
            - storing password_hash
            - storing role/status
            - enforcing unique usernames
        """
        try:
            employee_id = (
                self._selected_employee_id()
            )

            username = self._username()

            password = (
                self.password_entry
                .get()
            )

            if not password:
                raise ValueError(
                    "Enter a new password or "
                    "use Generate password."
                )

            role = self.role_menu.get()

            active = bool(
                self.active_checkbox.get()
            )

            user = (
                self._controller
                .create_user_with_password(
                    employee_id=employee_id,
                    username=username,
                    password=password,
                    role=role,
                    active=active,
                )
            )

            self.password_entry.delete(
                0,
                "end",
            )

            self._update_password_strength()

            self._message(
                (
                    f"Credentials saved for "
                    f"{user.get('username', username)}."
                ),
                Theme.SUCCESS,
            )

            self._refresh_all()

        except Exception as error:
            self._message(
                str(error),
                Theme.DANGER,
            )

    def _generate_credentials(self) -> None:
        try:
            employee_id = (
                self._selected_employee_id()
            )

            username = (
                self.username_entry
                .get()
                .strip()
            )

            role = self.role_menu.get()

            active = bool(
                self.active_checkbox.get()
            )

            if username:
                (
                    user,
                    password,
                ) = (
                    self._controller
                    .create_user_with_generated_password(
                        employee_id=employee_id,
                        username=username,
                        role=role,
                        active=active,
                    )
                )
            else:
                (
                    user,
                    password,
                ) = (
                    self._controller
                    .create_user_from_employee(
                        employee_id=employee_id,
                        role=role,
                        active=active,
                    )
                )

            self._password_popup(
                user.get(
                    "username",
                    username,
                ),
                password,
            )

            self._message(
                "Account credentials saved successfully.",
                Theme.SUCCESS,
            )

            self._refresh_all()

        except Exception as error:
            self._message(
                str(error),
                Theme.DANGER,
            )

    def _reset_password(
        self,
        user_id: str,
        username: str,
    ) -> None:
        try:
            password = (
                self._controller
                .reset_user_password_generated(
                    user_id
                )
            )

            self._password_popup(
                username,
                password,
            )

            self._message(
                f"Password reset for {username}.",
                Theme.SUCCESS,
            )

        except Exception as error:
            self._message(
                str(error),
                Theme.DANGER,
            )

    # ------------------------------------------------------------------
    # Account status
    # ------------------------------------------------------------------

    def _change_status(
        self,
        user_id: str,
        active: bool,
    ) -> None:
        try:
            self._controller.set_user_status(
                user_id,
                active,
            )

            self._message(
                (
                    "Account activated."
                    if active
                    else "Account deactivated."
                ),
                Theme.SUCCESS,
            )

            self._refresh_all()

        except Exception as error:
            self._message(
                str(error),
                Theme.DANGER,
            )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _delete_user(
        self,
        user_id: str,
        username: str,
    ) -> None:
        dialog = ctk.CTkToplevel(
            self
        )

        dialog.title(
            "Delete account"
        )

        dialog.geometry(
            "400x180"
        )

        dialog.resizable(
            False,
            False,
        )

        dialog.configure(
            fg_color=Theme.BG
        )

        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Delete this account?",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).pack(
            pady=(22, 8)
        )

        ctk.CTkLabel(
            dialog,
            text=(
                f"'{username}' will be permanently removed."
            ),
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).pack(
            pady=(0, 16)
        )

        buttons = ctk.CTkFrame(
            dialog,
            fg_color="transparent",
        )
        buttons.pack()

        ctk.CTkButton(
            buttons,
            text="Cancel",
            command=dialog.destroy,
        ).pack(
            side="left",
            padx=6,
        )

        def confirm() -> None:
            dialog.destroy()

            try:
                self._controller.delete_user(
                    user_id
                )

                self._message(
                    f"Deleted {username}.",
                    Theme.SUCCESS,
                )

                self._refresh_all()

            except Exception as error:
                self._message(
                    str(error),
                    Theme.DANGER,
                )

        ctk.CTkButton(
            buttons,
            text="Delete",
            fg_color=Theme.DANGER,
            hover_color=Theme.DANGER_HOVER,
            command=confirm,
        ).pack(
            side="left",
            padx=6,
        )

    # ------------------------------------------------------------------
    # Generated password popup
    # ------------------------------------------------------------------

    def _password_popup(
        self,
        username: str,
        password: str,
    ) -> None:
        popup = ctk.CTkToplevel(
            self
        )

        popup.title(
            "Generated password"
        )

        popup.geometry(
            "440x250"
        )

        popup.resizable(
            False,
            False,
        )

        popup.configure(
            fg_color=Theme.BG
        )

        popup.transient(self)
        popup.grab_set()

        ctk.CTkLabel(
            popup,
            text="Save this password now",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).pack(
            pady=(24, 6)
        )

        ctk.CTkLabel(
            popup,
            text=f"Username: {username}",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).pack(
            pady=4
        )

        value = ctk.CTkEntry(
            popup,
            width=330,
            height=42,
            justify="center",
            font=("Consolas", 14, "bold"),
        )

        value.insert(
            0,
            password,
        )

        value.configure(
            state="readonly"
        )

        value.pack(
            pady=10
        )

        ctk.CTkLabel(
            popup,
            text=(
                "Share it securely. "
                "The password is not stored in plain text."
            ),
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).pack(
            pady=(0, 12)
        )

        ctk.CTkButton(
            popup,
            text="Close",
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=popup.destroy,
        ).pack()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_employee_id(self) -> str:
        selected = (
            self.employee_menu
            .get()
        )

        if selected.startswith(
            "Select Employee"
        ):
            raise ValueError(
                "Select an employee first."
            )

        employee_id = (
            selected
            .split(":", 1)[0]
            .strip()
        )

        if not employee_id:
            raise ValueError(
                "The selected employee does not have "
                "a valid employee_id."
            )

        return employee_id

    def _username(self) -> str:
        username = (
            self.username_entry
            .get()
            .strip()
            .lower()
        )

        if username:
            return username

        employee = self._employees.get(
            self._selected_employee_id()
        )

        if not employee:
            raise ValueError(
                "Could not identify the selected employee."
            )

        return self._generate_username(
            employee
        )

    @staticmethod
    def _generate_username(
        employee: dict[str, Any],
    ) -> str:
        """
        Generate a username from the real MongoDB employee
        identity.

        Examples:

            Siyanda Nkosi
            -> siyanda.nkosi

            John Smith
            -> john.smith
        """
        first_name = str(
            employee.get(
                "first_name",
                "",
            )
            or ""
        ).strip()

        surname = str(
            employee.get(
                "surname",
                "",
            )
            or ""
        ).strip()

        if first_name and surname:
            first = (
                first_name
                .lower()
                .replace("&", "and")
                .replace(" ", "")
            )

            last = (
                surname
                .lower()
                .replace("&", "and")
                .replace(" ", "")
            )

            return f"{first}.{last}"

        full_name = str(
            employee.get(
                "full_name",
                "",
            )
            or ""
        ).strip()

        parts = [
            part
            for part in (
                full_name
                .lower()
                .replace("&", "and")
                .split()
            )
            if part
        ]

        if len(parts) >= 2:
            return f"{parts[0]}.{parts[-1]}"

        if parts:
            return parts[0]

        raise ValueError(
            "The employee does not have a usable name "
            "for username generation."
        )

    @staticmethod
    def _get_employee_id(
        employee: dict[str, Any],
    ) -> Any:
        """
        Return the application's employee_id.

        MongoDB's ObjectId (_id) is intentionally NOT used
        as the employee relationship.
        """
        value = employee.get(
            "employee_id"
        )

        if value is not None:
            return value

        # Support an existing application field called "id"
        # if the employee collection uses it as the business ID.
        value = employee.get(
            "id"
        )

        if value is not None:
            return value

        return None

    @staticmethod
    def _employee_name(
        employee: dict[str, Any],
    ) -> str:
        full_name = str(
            employee.get(
                "full_name",
                "",
            )
            or ""
        ).strip()

        if full_name:
            return full_name

        first_name = str(
            employee.get(
                "first_name",
                "",
            )
            or ""
        ).strip()

        surname = str(
            employee.get(
                "surname",
                "",
            )
            or ""
        ).strip()

        name = (
            f"{first_name} {surname}"
        ).strip()

        return name or "Unnamed employee"

    @staticmethod
    def _user_name(
        user: dict[str, Any],
    ) -> str:
        full_name = str(
            user.get(
                "full_name",
                "",
            )
            or ""
        ).strip()

        if full_name:
            return full_name

        first_name = str(
            user.get(
                "first_name",
                "",
            )
            or ""
        ).strip()

        surname = str(
            user.get(
                "surname",
                "",
            )
            or ""
        ).strip()

        name = (
            f"{first_name} {surname}"
        ).strip()

        return name or "Untangled employee"

    @staticmethod
    def _mongo_user_id(
        user: dict[str, Any],
    ) -> str:
        """
        Return the MongoDB user identifier used by the
        controller's account-management methods.

        The user document's _id is used here because this
        identifies the USER document, not the employee.
        """
        value = user.get("_id")

        if value is None:
            value = user.get("id")

        if value is None:
            raise ValueError(
                "User account does not contain a valid MongoDB user ID."
            )

        return str(value)

    def _toggle_password(self) -> None:
        self.password_entry.configure(
            show=(
                ""
                if self.show_password.get()
                else "*"
            )
        )

    def _update_password_strength(
        self,
        _event: object = None,
    ) -> None:
        password = (
            self.password_entry
            .get()
        )

        if not password:
            self.password_hint.configure(
                text=(
                    "Use 8+ characters with upper, "
                    "lower, number, and symbol."
                ),
                text_color=Theme.MUTED_TEXT,
            )
            return

        checks = (
            len(password) >= 8,
            any(
                character.isupper()
                for character in password
            ),
            any(
                character.islower()
                for character in password
            ),
            any(
                character.isdigit()
                for character in password
            ),
            any(
                not character.isalnum()
                for character in password
            ),
        )

        score = sum(checks)

        if score == 5:
            message = "Strong password"
            color = Theme.SUCCESS

        elif score >= 3:
            message = (
                "Medium password — add more "
                "character types"
            )
            color = Theme.WARNING

        else:
            message = (
                "Weak password — add uppercase, "
                "number, and symbol"
            )
            color = Theme.DANGER

        self.password_hint.configure(
            text=message,
            text_color=color,
        )

    # ------------------------------------------------------------------
    # Responsive layout
    # ------------------------------------------------------------------

    def _schedule_resize(
        self,
        _event: object = None,
    ) -> None:
        if self._resize_job is not None:
            try:
                self.after_cancel(
                    self._resize_job
                )
            except Exception:
                pass

        self._resize_job = self.after(
            80,
            self._apply_responsive_layout,
        )

    def _apply_responsive_layout(
        self,
    ) -> None:
        self._resize_job = None

        compact = (
            self.winfo_width() < 760
        )

        if compact == self._compact:
            return

        self._compact = compact

        padding = (
            14
            if compact
            else 28
        )

        for widget in (
            self.header,
            self.form,
            self.stats,
            self.accounts,
        ):
            widget.grid_configure(
                padx=padding
            )

        if compact:
            self._compact_form_layout()
        else:
            self._desktop_form_layout()

    def _desktop_form_layout(self) -> None:
        self.employee_label.grid(
            row=2,
            column=0,
            padx=(18, 8),
            sticky="w",
        )

        self.username_label.grid(
            row=2,
            column=1,
            padx=(8, 18),
            sticky="w",
        )

        self.employee_menu.grid(
            row=3,
            column=0,
            padx=(18, 8),
            pady=(4, 10),
            sticky="ew",
        )

        self.username_entry.grid(
            row=3,
            column=1,
            padx=(8, 18),
            pady=(4, 10),
            sticky="ew",
        )

        self.password_label.grid(
            row=4,
            column=0,
            padx=(18, 8),
            sticky="w",
        )

        self.role_label.grid(
            row=4,
            column=1,
            padx=(8, 18),
            sticky="w",
        )

        self.password_entry.grid(
            row=5,
            column=0,
            padx=(18, 8),
            pady=(4, 4),
            sticky="ew",
        )

        self.role_menu.grid(
            row=5,
            column=1,
            padx=(8, 18),
            pady=(4, 4),
            sticky="ew",
        )

        self.password_hint.grid(
            row=6,
            column=0,
            padx=(18, 8),
            pady=(0, 8),
            sticky="w",
        )

        self.show_password.grid(
            row=6,
            column=1,
            padx=(8, 18),
            pady=(0, 8),
            sticky="w",
        )

        self.active_checkbox.grid(
            row=7,
            column=0,
            padx=18,
            pady=(0, 14),
            sticky="w",
        )

        self.actions.grid(
            row=7,
            column=1,
            padx=(8, 18),
            pady=(0, 14),
            sticky="ew",
        )

        self.status_label.grid(
            row=8,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 14),
            sticky="w",
        )

    def _compact_form_layout(self) -> None:
        self.employee_label.grid(
            row=2,
            column=0,
            columnspan=2,
            padx=18,
            sticky="w",
        )

        self.employee_menu.grid(
            row=3,
            column=0,
            columnspan=2,
            padx=18,
            pady=(4, 10),
            sticky="ew",
        )

        self.username_label.grid(
            row=4,
            column=0,
            columnspan=2,
            padx=18,
            sticky="w",
        )

        self.username_entry.grid(
            row=5,
            column=0,
            columnspan=2,
            padx=18,
            pady=(4, 10),
            sticky="ew",
        )

        self.password_label.grid(
            row=6,
            column=0,
            columnspan=2,
            padx=18,
            sticky="w",
        )

        self.password_entry.grid(
            row=7,
            column=0,
            columnspan=2,
            padx=18,
            pady=(4, 4),
            sticky="ew",
        )

        self.password_hint.grid(
            row=8,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 6),
            sticky="w",
        )

        self.show_password.grid(
            row=9,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 10),
            sticky="w",
        )

        self.role_label.grid(
            row=10,
            column=0,
            columnspan=2,
            padx=18,
            sticky="w",
        )

        self.role_menu.grid(
            row=11,
            column=0,
            columnspan=2,
            padx=18,
            pady=(4, 10),
            sticky="ew",
        )

        self.active_checkbox.grid(
            row=12,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 10),
            sticky="w",
        )

        self.actions.grid(
            row=13,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 12),
            sticky="ew",
        )

        self.status_label.grid(
            row=14,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 14),
            sticky="w",
        )

    # ------------------------------------------------------------------
    # Generic UI helpers
    # ------------------------------------------------------------------

    def _label(
        self,
        text: str,
    ) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            self.form,
            text=text,
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        )

    def _message(
        self,
        text: str,
        color: str,
    ) -> None:
        self.status_label.configure(
            text=text,
            text_color=color,
        )

    @staticmethod
    def _display_date(
        value: object,
    ) -> str:
        if not value:
            return "Never"

        if isinstance(
            value,
            datetime,
        ):
            return value.strftime(
                "%Y-%m-%d %H:%M"
            )

        try:
            parsed = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

            return parsed.strftime(
                "%Y-%m-%d %H:%M"
            )

        except (
            ValueError,
            TypeError,
        ):
            return str(value)[:16]
