"""Interactive employee directory card."""

from collections.abc import Callable

import customtkinter as ctk

from app.models.employee import Employee
from app.utils.theme import Theme


class EmployeeCard(ctk.CTkFrame):
    """Compact employee summary with a prominent live-presence indicator."""

    PRESENCE_COLORS = {
        "online": "#22C55E",
        "away": "#EAB308",
        "dnd": "#EF4444",
        "offline": "#6B7280",
    }

    def __init__(
        self,
        master: object,
        employee: Employee,
        on_click: Callable[[object], None],
        selected: bool = False,
    ) -> None:
        self._employee = employee
        self._on_click = on_click
        self._selected = selected
        super().__init__(
            master,
            fg_color=Theme.PANEL_ALT if selected else Theme.PANEL,
            border_color=Theme.ACCENT if selected else Theme.BORDER,
            border_width=2 if selected else 1,
            corner_radius=Theme.RADIUS,
        )
        self._build_layout()
        self._bind_click_handler(self)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        avatar_wrap = ctk.CTkFrame(self, width=66, height=66, fg_color="transparent")
        avatar_wrap.grid(row=0, column=0, rowspan=3, padx=(14, 10), pady=14, sticky="n")
        avatar_wrap.grid_propagate(False)
        ctk.CTkLabel(
            avatar_wrap, text=self._initials(), width=56, height=56,
            fg_color=Theme.PANEL_ALT if not self._selected else Theme.BORDER,
            corner_radius=28, text_color=Theme.TEXT,
            font=("Segoe UI", 16, "bold"),
        ).place(x=2, y=2)
        ctk.CTkLabel(
            avatar_wrap, text="●", width=20, height=20,
            text_color=self.PRESENCE_COLORS.get(self._employee.presence, "#6B7280"),
            fg_color=Theme.PANEL if not self._selected else Theme.PANEL_ALT,
            corner_radius=10, font=("Segoe UI", 17, "bold"),
        ).place(x=43, y=42)

        name_line = ctk.CTkFrame(self, fg_color="transparent")
        name_line.grid(row=0, column=1, padx=(0, 14), pady=(14, 1), sticky="ew")
        name_line.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            name_line, text=self._employee.full_name or "Unnamed employee",
            text_color=Theme.TEXT, font=("Segoe UI", 15, "bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            name_line, text=f"@{self._employee.username.lstrip('@')}",
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 11), anchor="e",
        ).grid(row=0, column=1, padx=(8, 0), sticky="e")

        ctk.CTkLabel(
            self, text=self._employee.position or "Team Member",
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w",
        ).grid(row=1, column=1, padx=(0, 14), sticky="ew")
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=1, padx=(0, 14), pady=(7, 14), sticky="ew")
        ctk.CTkLabel(
            footer, text=self._employee.team or self._employee.department or "General",
            fg_color=Theme.PANEL_ALT if not self._selected else Theme.ACCENT,
            text_color=Theme.TEXT if not self._selected else "#FFFFFF",
            corner_radius=9, padx=9, pady=3, font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        presence_label = {
            "online": "Online", "away": "Away", "dnd": "Do Not Disturb",
            "offline": "Offline",
        }.get(self._employee.presence, "Offline")
        ctk.CTkLabel(
            footer, text=presence_label,
            text_color=self.PRESENCE_COLORS.get(self._employee.presence, "#6B7280"),
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.configure(
            fg_color=Theme.PANEL_ALT if selected else Theme.PANEL,
            border_color=Theme.ACCENT if selected else Theme.BORDER,
            border_width=2 if selected else 1,
        )

    def _bind_click_handler(self, widget: object) -> None:
        if isinstance(widget, ctk.CTkBaseClass):
            widget.bind("<Button-1>", self._handle_click)
            for child in widget.winfo_children():
                self._bind_click_handler(child)

    def _handle_click(self, _event: object) -> None:
        if self._employee.id is not None:
            self._on_click(self._employee.id)

    def set_selected(self, selected: bool) -> None:
        """Show which employee is currently open in the preview pane."""
        self._selected = selected
        self.configure(
            fg_color=Theme.PANEL_ALT if selected else Theme.PANEL,
            border_color=Theme.ACCENT if selected else Theme.BORDER,
            border_width=2 if selected else 1,
        )

    def _initials(self) -> str:
        initials = f"{self._employee.first_name[:1]}{self._employee.last_name[:1]}".upper()
        if not initials:
            initials = "".join(part[:1] for part in self._employee.full_name.split()[:2]).upper()
        return initials or "?"
