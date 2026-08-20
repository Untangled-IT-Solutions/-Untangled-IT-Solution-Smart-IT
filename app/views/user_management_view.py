# app/views/user_management_view.py
"""User management view for creating and managing users."""

import customtkinter as ctk
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.utils.theme import Theme


class UserManagementView(ctk.CTkFrame):
    """View for managing users with password generation."""

    def __init__(self, master, controller):
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._selected_user_id: Optional[str] = None
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self._build_layout()
        self._refresh_data()

    def _build_layout(self) -> None:
        """Build the user management layout."""
        # Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=28, pady=(20, 0))
        title_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            title_frame,
            text="👤 User Management",
            text_color=Theme.TEXT,
            font=Theme.FONT_TITLE,
        ).grid(row=0, column=0, sticky="w")
        
        ctk.CTkLabel(
            title_frame,
            text="Create and manage user accounts",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).grid(row=1, column=0, sticky="w")
        
        # Refresh button
        ctk.CTkButton(
            title_frame,
            text="🔄 Refresh",
            width=100,
            height=32,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._refresh_data,
        ).grid(row=0, column=1, rowspan=2, padx=(0, 0), sticky="e")

        # User Creation Panel
        self._build_creation_panel()

        # Statistics Panel
        self._build_statistics_panel()

        # User List
        self._build_user_list()

    def _build_creation_panel(self) -> None:
        """Build the user creation panel."""
        panel = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        panel.grid(row=1, column=0, padx=28, pady=(16, 0), sticky="ew")
        panel.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            panel,
            text="Create New User",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w")

        # Employee selection
        ctk.CTkLabel(
            panel,
            text="Employee",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=1, column=0, padx=(16, 8), pady=4, sticky="w")
        
        self.employee_menu = ctk.CTkOptionMenu(
            panel,
            values=["Select Employee..."],
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
            dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
        )
        self.employee_menu.grid(row=2, column=0, padx=(16, 8), pady=(0, 12), sticky="ew")

        # Username
        ctk.CTkLabel(
            panel,
            text="Username",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        
        self.username_entry = ctk.CTkEntry(
            panel,
            height=38,
            placeholder_text="Auto-generated",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
        )
        self.username_entry.grid(row=2, column=1, padx=8, pady=(0, 12), sticky="ew")

        # Role selection
        ctk.CTkLabel(
            panel,
            text="Role",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=1, column=2, padx=8, pady=4, sticky="w")
        
        self.role_menu = ctk.CTkOptionMenu(
            panel,
            values=["Director", "Branch Manager", "Business Lead", "Operations Manager", "Staff", "Intern"],
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
            dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
        )
        self.role_menu.set("Staff")
        self.role_menu.grid(row=2, column=2, padx=8, pady=(0, 12), sticky="ew")

        # Action buttons
        button_frame = ctk.CTkFrame(panel, fg_color="transparent")
        button_frame.grid(row=2, column=3, padx=(8, 16), pady=(0, 12), sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        self.create_button = ctk.CTkButton(
            button_frame,
            text="Create with Password",
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._create_user_with_password,
        )
        self.create_button.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.generate_button = ctk.CTkButton(
            button_frame,
            text="Generate Password",
            fg_color=Theme.SUCCESS,
            hover_color="#2E7D32",
            command=self._create_user_generated,
        )
        self.generate_button.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        # Password input (for create with password)
        ctk.CTkLabel(
            panel,
            text="Password",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=3, column=0, columnspan=2, padx=(16, 8), pady=(4, 4), sticky="w")
        
        self.password_entry = ctk.CTkEntry(
            panel,
            height=38,
            placeholder_text="Enter password...",
            show="*",
            fg_color=Theme.PANEL_ALT,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
        )
        self.password_entry.grid(row=4, column=0, columnspan=2, padx=(16, 8), pady=(0, 12), sticky="ew")
        
        # Active checkbox
        self.active_checkbox = ctk.CTkCheckBox(
            panel,
            text="Active",
            text_color=Theme.TEXT,
        )
        self.active_checkbox.select()
        self.active_checkbox.grid(row=4, column=2, padx=8, pady=(0, 12), sticky="w")

        # Status message
        self.status_label = ctk.CTkLabel(
            panel,
            text="",
            text_color=Theme.TEXT,
            font=Theme.FONT_SMALL,
        )
        self.status_label.grid(row=5, column=0, columnspan=4, padx=16, pady=(0, 12), sticky="w")

    def _build_statistics_panel(self) -> None:
        """Build the statistics panel."""
        panel = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        panel.grid(row=2, column=0, padx=28, pady=(16, 0), sticky="ew")
        panel.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(
            panel,
            text="Statistics",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, columnspan=4, padx=16, pady=(8, 4), sticky="w")

        # Stats will be updated dynamically
        self.stats_labels = {}
        stat_fields = [
            ("total_users", "Total Users"),
            ("active_users", "Active Users"),
            ("inactive_users", "Inactive Users"),
            ("last_login", "Last Login"),
        ]

        for idx, (key, label) in enumerate(stat_fields):
            container = ctk.CTkFrame(panel, fg_color="transparent")
            container.grid(row=1, column=idx, padx=16, pady=8, sticky="ew")
            
            ctk.CTkLabel(
                container,
                text=label,
                text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_SMALL,
            ).pack(anchor="w")
            
            self.stats_labels[key] = ctk.CTkLabel(
                container,
                text="...",
                text_color=Theme.TEXT,
                font=("Segoe UI", 18, "bold"),
            )
            self.stats_labels[key].pack(anchor="w")

    def _build_user_list(self) -> None:
        """Build the user list with actions."""
        list_frame = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        list_frame.grid(row=3, column=0, padx=28, pady=(16, 28), sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)

        # Header
        header_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="User Accounts",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, sticky="w")

        # Filter
        self.filter_menu = ctk.CTkOptionMenu(
            header_frame,
            values=["All Users", "Active Only", "Inactive Only"],
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
            dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
            command=self._refresh_data,
        )
        self.filter_menu.set("Active Only")
        self.filter_menu.grid(row=0, column=1, padx=8, sticky="e")

        # Scrollable user list
        self.user_list_frame = ctk.CTkScrollableFrame(
            list_frame,
            fg_color="transparent",
            scrollbar_button_color=Theme.PANEL_ALT,
            scrollbar_button_hover_color=Theme.BORDER,
        )
        self.user_list_frame.grid(row=1, column=0, padx=8, pady=(0, 12), sticky="nsew")

    def _refresh_data(self, *args) -> None:
        """Refresh all data in the view."""
        if not self._controller:
            ctk.CTkLabel(
                self,
                text="⚠️ User Management not available. MongoDB may not be connected.",
                text_color=Theme.DANGER,
                font=Theme.FONT_BODY,
            ).grid(row=4, column=0, padx=28, pady=20)
            return
            
        # Refresh employees dropdown
        self._refresh_employee_options()
        
        # Refresh user list
        self._refresh_user_list()
        
        # Refresh statistics
        self._refresh_statistics()

    def _refresh_employee_options(self) -> None:
        """Refresh the employee dropdown."""
        if not self._controller:
            return
            
        try:
            employees = self._controller.get_employees_without_accounts()
            options = ["Select Employee..."] + [
                f"{str(emp['_id'])}: {emp['full_name']} ({emp['position']})"
                for emp in employees
            ]
            self.employee_menu.configure(values=options)
            if options:
                self.employee_menu.set(options[0])
        except Exception as e:
            print(f"Error refreshing employees: {e}")

    def _refresh_user_list(self) -> None:
        """Refresh the user list."""
        if not self._controller:
            return
            
        # Clear existing list
        for widget in self.user_list_frame.winfo_children():
            widget.destroy()

        try:
            # Get users
            filter_mode = self.filter_menu.get()
            include_inactive = filter_mode in ["All Users", "Inactive Only"]
            users = self._controller.get_all_users(include_inactive)
            
            # Apply filter
            if filter_mode == "Active Only":
                users = [u for u in users if u.get("status") == "active"]
            elif filter_mode == "Inactive Only":
                users = [u for u in users if u.get("status") != "active"]

            if not users:
                ctk.CTkLabel(
                    self.user_list_frame,
                    text="No users found",
                    text_color=Theme.MUTED_TEXT,
                    font=Theme.FONT_BODY,
                ).pack(pady=20)
                return

            # Create user cards
            for user in users:
                self._create_user_card(user)
        except Exception as e:
            print(f"Error refreshing user list: {e}")

    def _create_user_card(self, user: Dict[str, Any]) -> None:
        """Create a user card in the list."""
        card = ctk.CTkFrame(
            self.user_list_frame,
            fg_color=Theme.PANEL_ALT,
            corner_radius=Theme.RADIUS,
            border_color=Theme.BORDER if user.get("_id") == self._selected_user_id else "transparent",
            border_width=2,
        )
        card.pack(fill="x", pady=4, padx=4)
        card.grid_columnconfigure(0, weight=1)

        # User info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=0, padx=16, pady=8, sticky="ew")
        info_frame.grid_columnconfigure(1, weight=1)

        # Status indicator
        status_color = Theme.SUCCESS if user.get("status") == "active" else Theme.DANGER
        ctk.CTkLabel(
            info_frame,
            text="●" if user.get("status") == "active" else "○",
            text_color=status_color,
            font=("Segoe UI", 14),
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")

        # Username and name
        name_text = f"{user.get('username', 'Unknown')} - {user.get('full_name', '')}"
        if user.get('employee_full_name'):
            name_text = f"{user.get('username', 'Unknown')} - {user.get('employee_full_name')}"
        
        ctk.CTkLabel(
            info_frame,
            text=name_text,
            text_color=Theme.TEXT,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=1, sticky="w")

        # Role
        role_badge = ctk.CTkFrame(
            info_frame,
            fg_color=Theme.ACCENT,
            corner_radius=Theme.RADIUS,
        )
        role_badge.grid(row=0, column=2, padx=8, sticky="e")
        ctk.CTkLabel(
            role_badge,
            text=user.get("role", "Staff"),
            text_color=Theme.TEXT,
            font=("Segoe UI", 11),
            padx=8,
            pady=2,
        ).pack()

        # Action buttons
        action_frame = ctk.CTkFrame(card, fg_color="transparent")
        action_frame.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)

        # Show more info in expandable section
        detail_text = f"Department: {user.get('department', 'N/A')} | Last Login: {user.get('last_login_at', 'Never')}"
        if user.get('last_login_at'):
            try:
                dt = datetime.fromisoformat(user['last_login_at'].replace('Z', '+00:00'))
                detail_text = f"Department: {user.get('department', 'N/A')} | Last Login: {dt.strftime('%Y-%m-%d %H:%M')}"
            except:
                pass

        ctk.CTkLabel(
            action_frame,
            text=detail_text,
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=0, column=0, sticky="w")

        # Action buttons
        button_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        button_frame.grid(row=0, column=1, sticky="e")

        # Reset password button
        reset_btn = ctk.CTkButton(
            button_frame,
            text="Reset Password",
            width=100,
            height=28,
            fg_color=Theme.WARNING,
            hover_color="#F57C00",
            font=Theme.FONT_SMALL,
            command=lambda uid=str(user["_id"]): self._reset_password(uid),
        )
        reset_btn.pack(side="left", padx=4)

        # Toggle status button
        status_text = "Deactivate" if user.get("status") == "active" else "Activate"
        status_color = Theme.DANGER if user.get("status") == "active" else Theme.SUCCESS
        status_btn = ctk.CTkButton(
            button_frame,
            text=status_text,
            width=90,
            height=28,
            fg_color=status_color,
            hover_color="#C62828" if user.get("status") == "active" else "#2E7D32",
            font=Theme.FONT_SMALL,
            command=lambda uid=str(user["_id"]), status=user.get("status"): 
                self._toggle_user_status(uid, status != "active"),
        )
        status_btn.pack(side="left", padx=4)

        # Delete button (only for admins)
        del_btn = ctk.CTkButton(
            button_frame,
            text="🗑️",
            width=32,
            height=28,
            fg_color=Theme.DANGER,
            hover_color="#C62828",
            font=Theme.FONT_SMALL,
            command=lambda uid=str(user["_id"]): self._delete_user(uid),
        )
        del_btn.pack(side="left", padx=4)

    def _refresh_statistics(self) -> None:
        """Refresh the statistics panel."""
        if not self._controller:
            return
            
        try:
            stats = self._controller.get_user_statistics()
            
            self.stats_labels["total_users"].configure(text=str(stats.get("total_users", 0)))
            self.stats_labels["active_users"].configure(text=str(stats.get("active_users", 0)))
            self.stats_labels["inactive_users"].configure(text=str(stats.get("inactive_users", 0)))
            
            last_login = stats.get("last_login")
            if last_login:
                try:
                    dt = datetime.fromisoformat(last_login.replace('Z', '+00:00'))
                    self.stats_labels["last_login"].configure(text=dt.strftime("%Y-%m-%d %H:%M"))
                except:
                    self.stats_labels["last_login"].configure(text=str(last_login)[:16])
            else:
                self.stats_labels["last_login"].configure(text="Never")
        except Exception as e:
            print(f"Error refreshing statistics: {e}")

    def _create_user_with_password(self) -> None:
        """Create a user with a specific password."""
        if not self._controller:
            self.status_label.configure(
                text="❌ User Management not available",
                text_color=Theme.DANGER,
            )
            return
            
        try:
            # Get selected employee
            employee_selection = self.employee_menu.get()
            if employee_selection.startswith("Select Employee"):
                raise ValueError("Please select an employee.")
            
            employee_id = employee_selection.split(":")[0]
            username = self.username_entry.get().strip()
            if not username:
                # Auto-generate username
                employee = self._controller.get_employee_by_id(employee_id)
                if employee:
                    username = self._controller._generate_username(employee["full_name"])
            
            password = self.password_entry.get()
            if not password:
                raise ValueError("Please enter a password.")
            
            role = self.role_menu.get()
            active = bool(self.active_checkbox.get())
            
            user = self._controller.create_user_with_password(
                employee_id=employee_id,
                username=username,
                password=password,
                role=role,
                active=active,
            )
            
            self.status_label.configure(
                text=f"✅ User {username} created successfully!",
                text_color=Theme.SUCCESS,
            )
            self.password_entry.delete(0, "end")
            self._refresh_data()
            
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Error: {str(e)}",
                text_color=Theme.DANGER,
            )

    def _create_user_generated(self) -> None:
        """Create a user with an auto-generated password."""
        if not self._controller:
            self.status_label.configure(
                text="❌ User Management not available",
                text_color=Theme.DANGER,
            )
            return
            
        try:
            # Get selected employee
            employee_selection = self.employee_menu.get()
            if employee_selection.startswith("Select Employee"):
                raise ValueError("Please select an employee.")
            
            employee_id = employee_selection.split(":")[0]
            username = self.username_entry.get().strip()
            role = self.role_menu.get()
            active = bool(self.active_checkbox.get())
            
            if username:
                # Create with provided username
                user, password = self._controller.create_user_with_generated_password(
                    employee_id=employee_id,
                    username=username,
                    role=role,
                    active=active,
                )
            else:
                # Create from employee
                user, password = self._controller.create_user_from_employee(
                    employee_id=employee_id,
                    role=role,
                    active=active,
                )
            
            self.status_label.configure(
                text=f"✅ User created! Password: {password}",
                text_color=Theme.SUCCESS,
            )
            self.password_entry.delete(0, "end")
            
            # Show password in a popup
            self._show_password_popup(user.get("username", "Unknown"), password)
            
            self._refresh_data()
            
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Error: {str(e)}",
                text_color=Theme.DANGER,
            )

    def _show_password_popup(self, username: str, password: str) -> None:
        """Show a popup with the generated password."""
        popup = ctk.CTkToplevel(self)
        popup.title("Generated Password")
        popup.geometry("400x200")
        popup.resizable(False, False)
        popup.configure(fg_color=Theme.BG)
        
        # Make it modal
        popup.transient(self)
        popup.grab_set()
        
        ctk.CTkLabel(
            popup,
            text="🔑 User Created Successfully",
            text_color=Theme.SUCCESS,
            font=Theme.FONT_HEADING,
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            popup,
            text=f"Username: {username}",
            text_color=Theme.TEXT,
            font=Theme.FONT_BODY,
        ).pack(pady=5)
        
        ctk.CTkLabel(
            popup,
            text=f"Password: {password}",
            text_color=Theme.TEXT,
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=5)
        
        ctk.CTkLabel(
            popup,
            text="Please save this password securely.\nThe user will be prompted to change it on first login.",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
            justify="center",
        ).pack(pady=10)
        
        ctk.CTkButton(
            popup,
            text="OK",
            width=100,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=popup.destroy,
        ).pack(pady=10)

    def _reset_password(self, user_id: str) -> None:
        """Reset a user's password."""
        if not self._controller:
            return
            
        try:
            # Confirm with dialog
            confirm = ctk.CTkToplevel(self)
            confirm.title("Confirm Password Reset")
            confirm.geometry("350x150")
            confirm.resizable(False, False)
            confirm.configure(fg_color=Theme.BG)
            confirm.transient(self)
            confirm.grab_set()
            
            ctk.CTkLabel(
                confirm,
                text="Reset user password?",
                text_color=Theme.TEXT,
                font=Theme.FONT_HEADING,
            ).pack(pady=(20, 10))
            
            ctk.CTkLabel(
                confirm,
                text="A new password will be generated.",
                text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_BODY,
            ).pack(pady=5)
            
            button_frame = ctk.CTkFrame(confirm, fg_color="transparent")
            button_frame.pack(pady=10)
            
            def do_reset():
                confirm.destroy()
                try:
                    new_password = self._controller.reset_user_password_generated(user_id)
                    self._show_password_popup("User", new_password)
                    self._refresh_data()
                except Exception as e:
                    self.status_label.configure(
                        text=f"❌ Error: {str(e)}",
                        text_color=Theme.DANGER,
                    )
            
            ctk.CTkButton(
                button_frame,
                text="Reset Password",
                fg_color=Theme.WARNING,
                hover_color="#F57C00",
                command=do_reset,
            ).pack(side="left", padx=5)
            
            ctk.CTkButton(
                button_frame,
                text="Cancel",
                fg_color=Theme.PANEL_ALT,
                hover_color=Theme.BORDER,
                text_color=Theme.TEXT,
                command=confirm.destroy,
            ).pack(side="left", padx=5)
            
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Error: {str(e)}",
                text_color=Theme.DANGER,
            )

    def _toggle_user_status(self, user_id: str, active: bool) -> None:
        """Toggle user active status."""
        if not self._controller:
            return
            
        try:
            self._controller.set_user_status(user_id, active)
            status_text = "activated" if active else "deactivated"
            self.status_label.configure(
                text=f"✅ User {status_text} successfully.",
                text_color=Theme.SUCCESS,
            )
            self._refresh_data()
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Error: {str(e)}",
                text_color=Theme.DANGER,
            )

    def _delete_user(self, user_id: str) -> None:
        """Delete a user account."""
        if not self._controller:
            return
            
        try:
            # Confirm deletion
            confirm = ctk.CTkToplevel(self)
            confirm.title("Confirm Deletion")
            confirm.geometry("350x150")
            confirm.resizable(False, False)
            confirm.configure(fg_color=Theme.BG)
            confirm.transient(self)
            confirm.grab_set()
            
            ctk.CTkLabel(
                confirm,
                text="⚠️ Delete User Account?",
                text_color=Theme.DANGER,
                font=Theme.FONT_HEADING,
            ).pack(pady=(20, 10))
            
            ctk.CTkLabel(
                confirm,
                text="This action cannot be undone.",
                text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_BODY,
            ).pack(pady=5)
            
            button_frame = ctk.CTkFrame(confirm, fg_color="transparent")
            button_frame.pack(pady=10)
            
            def do_delete():
                confirm.destroy()
                try:
                    self._controller.delete_user(user_id)
                    self.status_label.configure(
                        text="✅ User deleted successfully.",
                        text_color=Theme.SUCCESS,
                    )
                    self._refresh_data()
                except Exception as e:
                    self.status_label.configure(
                        text=f"❌ Error: {str(e)}",
                        text_color=Theme.DANGER,
                    )
            
            ctk.CTkButton(
                button_frame,
                text="Delete",
                fg_color=Theme.DANGER,
                hover_color="#C62828",
                command=do_delete,
            ).pack(side="left", padx=5)
            
            ctk.CTkButton(
                button_frame,
                text="Cancel",
                fg_color=Theme.PANEL_ALT,
                hover_color=Theme.BORDER,
                text_color=Theme.TEXT,
                command=confirm.destroy,
            ).pack(side="left", padx=5)
            
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Error: {str(e)}",
                text_color=Theme.DANGER,
            )