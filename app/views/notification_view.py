"""Notification centre view."""

import customtkinter as ctk

from app.controllers.notification_controller import NotificationController
from app.utils.theme import Theme
from app.widgets.notification_card import NotificationCard


class NotificationView(ctk.CTkFrame):
    """Displays central role-aware operational notifications and executive briefs."""

    def __init__(
        self,
        master: object,
        controller: NotificationController,
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
        ctk.CTkLabel(
            self, text="Notifications", text_color=Theme.TEXT, font=("Segoe UI", 30, "bold")
        ).grid(row=0, column=0, sticky="w")
        filters = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        filters.grid(row=1, column=0, pady=(20, 18), sticky="ew")
        self.role_filter = ctk.CTkOptionMenu(
            filters, values=list(self._controller.ROLE_OPTIONS), fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT, button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT, dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL, dropdown_hover_color=Theme.PANEL_ALT,
            command=lambda _value: self.refresh()
        )
        self.role_filter.set("All")
        self.role_filter.pack(side="left", padx=14, pady=12)
        self.unread_checkbox = ctk.CTkCheckBox(
            filters, text="Unread only", text_color=Theme.TEXT, command=self.refresh
        )
        self.unread_checkbox.pack(side="left", padx=(0, 14), pady=12)
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._list_frame.grid(row=2, column=0, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

    def _apply_initial_filters(self) -> None:
        role = self._initial_filters.get("role")
        if isinstance(role, str) and role in self.role_filter.cget("values"):
            self.role_filter.set(role)
        if self._initial_filters.get("unread_only"):
            self.unread_checkbox.select()

    def refresh(self) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()
        notifications = self._controller.get_notifications(
            self.role_filter.get(), bool(self.unread_checkbox.get())
        )
        if not notifications:
            ctk.CTkLabel(
                self._list_frame, text="No notifications found.", text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 14)
            ).grid(row=0, column=0, sticky="w")
            return
        for row, notification in enumerate(notifications):
            NotificationCard(self._list_frame, notification, self._mark_read).grid(
                row=row, column=0, sticky="ew", pady=(0, 10)
            )

    def _mark_read(self, notification_id: int) -> None:
        self._controller.mark_read(notification_id)
        self.refresh()
