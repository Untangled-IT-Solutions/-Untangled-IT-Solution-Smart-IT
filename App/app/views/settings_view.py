"""Settings workspace view."""

import customtkinter as ctk

from app.controllers.settings_controller import SettingsController
from app.utils.theme import Theme


class SettingsView(ctk.CTkFrame):
    """Application settings, theme preference, and system status."""

    def __init__(self, master: object, controller: SettingsController) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self, text="Settings", text_color=Theme.TEXT, font=Theme.FONT_TITLE).grid(row=0, column=0, sticky="w")
        panel = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        panel.grid(row=1, column=0, pady=(18, 0), sticky="ew")
        panel.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(panel, text="Theme", text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        self.theme_menu = ctk.CTkOptionMenu(
            panel,
            values=["dark", "light"],
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
            dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
            command=self._set_theme,
        )
        self.theme_menu.grid(row=0, column=1, padx=16, pady=(16, 6), sticky="ew")
        self.theme_menu.set(self._controller.get_theme_mode())
        last_row = 0
        for row, (label, value) in enumerate(self._controller.get_settings().items(), start=1):
            ctk.CTkLabel(panel, text=label, text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(row=row, column=0, padx=16, pady=6, sticky="w")
            ctk.CTkLabel(panel, text=value, text_color=Theme.TEXT, font=Theme.FONT_SMALL, wraplength=820, justify="left").grid(row=row, column=1, padx=16, pady=6, sticky="w")
            last_row = row
        ctk.CTkButton(
            panel,
            text="Check for Updates",
            font=Theme.FONT_BUTTON,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF",
            height=36,
            width=180,
            command=self._check_for_updates,
        ).grid(row=last_row + 1, column=0, columnspan=2, padx=16, pady=(12, 16), sticky="w")
        if self._controller.can_administer_accounts():
            self._build_account_admin()

    def _set_theme(self, mode: str) -> None:
        root = self.winfo_toplevel()
        if hasattr(root, "apply_theme"):
            root.apply_theme(mode)
        else:
            self._controller.set_theme_mode(mode)

    def _check_for_updates(self) -> None:
        if hasattr(self._controller, "check_for_updates"):
            self._controller.check_for_updates()

    def _build_account_admin(self) -> None:
        section = ctk.CTkScrollableFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        section.grid(row=2, column=0, pady=(18, 0), sticky="nsew")
        section.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkLabel(
            section,
            text="Account Administration",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, columnspan=4, padx=16, pady=(16, 10), sticky="w")

        employees = self._controller.get_employee_options() or ["No employees"]
        roles = self._controller.get_role_options()
        self.employee_menu = self._menu(section, employees, 1, 0)
        self.role_menu = self._menu(section, roles, 1, 1)
        self.username_entry = self._entry(section, "Username", 1, 2)
        self.password_entry = self._entry(section, "Password / reset password", 1, 3, show="*")
        self.active_checkbox = ctk.CTkCheckBox(section, text="Active", text_color=Theme.TEXT)
        self.active_checkbox.select()
        self.active_checkbox.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="w")
        ctk.CTkButton(
            section,
            text="Create Account",
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._create_account,
        ).grid(row=2, column=1, padx=8, pady=(0, 12), sticky="ew")

        self.account_menu = self._menu(section, self._account_options(), 3, 0)
        ctk.CTkButton(
            section,
            text="Reset Password",
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._reset_password,
        ).grid(row=3, column=1, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(
            section,
            text="Change Role",
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._change_role,
        ).grid(row=3, column=2, padx=8, pady=8, sticky="ew")
        ctk.CTkButton(
            section,
            text="Toggle Active",
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._toggle_active,
        ).grid(row=3, column=3, padx=16, pady=8, sticky="ew")
        self.account_status = ctk.CTkLabel(
            section, text="", text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL
        )
        self.account_status.grid(row=4, column=0, columnspan=4, padx=16, pady=(0, 10), sticky="w")
        self.accounts_frame = ctk.CTkFrame(section, fg_color="transparent")
        self.accounts_frame.grid(row=5, column=0, columnspan=4, padx=16, pady=(0, 16), sticky="ew")
        self.accounts_frame.grid_columnconfigure(0, weight=1)
        self._render_accounts()

    def _entry(
        self,
        master: object,
        placeholder: str,
        row: int,
        column: int,
        show: str | None = None,
    ) -> ctk.CTkEntry:
        entry = ctk.CTkEntry(
            master,
            height=38,
            placeholder_text=placeholder,
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
        )
        if show:
            entry.configure(show=show)
        entry.grid(row=row, column=column, padx=8 if column else 16, pady=(0, 10), sticky="ew")
        return entry

    def _menu(self, master: object, values: list[str], row: int, column: int) -> ctk.CTkOptionMenu:
        menu = ctk.CTkOptionMenu(
            master,
            values=values or [""],
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
            dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
        )
        menu.set((values or [""])[0])
        menu.grid(row=row, column=column, padx=8 if column else 16, pady=(0, 10), sticky="ew")
        return menu

    def _account_options(self) -> list[str]:
        return [
            f"{account.id}: {account.username} ({account.role}, {account.status})"
            for account in self._controller.get_accounts()
            if account.id is not None
        ] or ["No accounts"]

    def _selected_account_id(self) -> int:
        try:
            return int(self.account_menu.get().split(":", 1)[0])
        except (ValueError, IndexError) as error:
            raise ValueError("Select a valid account.") from error

    def _create_account(self) -> None:
        self._run_account_action(
            lambda: self._controller.create_account(
                self.employee_menu.get(),
                self.username_entry.get(),
                self.password_entry.get(),
                self.role_menu.get(),
                bool(self.active_checkbox.get()),
            ),
            "Account created.",
        )

    def _reset_password(self) -> None:
        self._run_account_action(
            lambda: self._controller.reset_password(self._selected_account_id(), self.password_entry.get()),
            "Password reset.",
        )

    def _change_role(self) -> None:
        self._run_account_action(
            lambda: self._controller.change_role(self._selected_account_id(), self.role_menu.get()),
            "Role changed.",
        )

    def _toggle_active(self) -> None:
        account_id = self._selected_account_id()
        account = next(
            account for account in self._controller.get_accounts() if account.id == account_id
        )
        self._run_account_action(
            lambda: self._controller.set_account_status(account_id, not account.is_active),
            "Account status changed.",
        )

    def _run_account_action(self, action: object, success_message: str) -> None:
        try:
            if callable(action):
                action()
        except (PermissionError, ValueError) as error:
            self.account_status.configure(text=str(error), text_color=Theme.DANGER)
            return
        self.account_status.configure(text=success_message, text_color=Theme.SUCCESS)
        self._refresh_account_admin()

    def _refresh_account_admin(self) -> None:
        options = self._account_options()
        self.account_menu.configure(values=options)
        self.account_menu.set(options[0])
        self._render_accounts()

    def _render_accounts(self) -> None:
        for child in self.accounts_frame.winfo_children():
            child.destroy()
        for row, account in enumerate(self._controller.get_accounts()):
            text = (
                f"{account.username} | {account.full_name} | {account.role} | "
                f"{account.status} | Last login: {account.last_login_at or 'Never'}"
            )
            ctk.CTkLabel(
                self.accounts_frame,
                text=text,
                text_color=Theme.TEXT,
                font=Theme.FONT_SMALL,
                anchor="w",
            ).grid(row=row, column=0, pady=(0, 6), sticky="ew")
