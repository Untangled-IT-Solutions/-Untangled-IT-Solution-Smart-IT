"""Office requests workspace view."""

from collections.abc import Callable

import customtkinter as ctk

from app.controllers.office_request_controller import OfficeRequestController
from app.utils.theme import Theme
from app.widgets.office_request_card import OfficeRequestCard


class OfficeRequestView(ctk.CTkFrame):
    """Creates office supply requests through the standard approval workflow."""

    def __init__(self, master: object, controller: OfficeRequestController) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._list_frame: ctk.CTkScrollableFrame | None = None
        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Office Requests", text_color=Theme.TEXT, font=("Segoe UI", 30, "bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header, text="New Request", height=40, fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER, command=self._open_request_form
        ).grid(row=0, column=1, sticky="e")
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._list_frame.grid(row=1, column=0, pady=(20, 0), sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

    def refresh(self) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()
        requests = self._controller.get_requests()
        if not requests:
            ctk.CTkLabel(
                self._list_frame, text="No office requests submitted.", text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 14)
            ).grid(row=0, column=0, sticky="w")
            return
        for row, request in enumerate(requests):
            OfficeRequestCard(self._list_frame, request).grid(row=row, column=0, pady=(0, 12), sticky="ew")

    def _open_request_form(self) -> None:
        OfficeRequestModal(self, self._controller, self.refresh)


class OfficeRequestModal(ctk.CTkToplevel):
    """Creates one office request and submits its approval record."""

    def __init__(
        self, master: object, controller: OfficeRequestController, on_saved: Callable[[], None]
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._on_saved = on_saved
        self.title("New Office Request")
        self.geometry("540x590")
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self, text="New Office Request", text_color=Theme.TEXT, font=("Segoe UI", 24, "bold")
        ).grid(row=0, column=0, padx=26, pady=(24, 10), sticky="w")
        form = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        form.grid(row=1, column=0, padx=26, sticky="ew")
        form.grid_columnconfigure(0, weight=1)
        self.item_entry = self._option(form, "Item", self._controller.get_items(), 0)
        self.quantity_entry = self._entry(form, "Quantity", 1, "1")
        self.requested_by_entry = self._option(form, "Requested By", self._controller.get_people_names(), 2)
        self.department_entry = self._option(form, "Department", self._controller.get_departments(), 3)
        ctk.CTkLabel(form, text="Notes", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12)).grid(
            row=8, column=0, padx=18, pady=(0, 5), sticky="w"
        )
        self.notes_entry = ctk.CTkTextbox(form, height=78, fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER, border_width=1)
        self.notes_entry.grid(row=9, column=0, padx=18, pady=(0, 12), sticky="ew")
        self.requires_director = ctk.CTkCheckBox(form, text="Director approval required", text_color=Theme.TEXT)
        self.requires_director.grid(row=10, column=0, padx=18, pady=(0, 14), sticky="w")
        self.error_label = ctk.CTkLabel(self, text="", text_color=Theme.DANGER, font=("Segoe UI", 12))
        self.error_label.grid(row=2, column=0, padx=26, pady=(8, 0), sticky="w")
        ctk.CTkButton(
            self, text="Submit Request", height=40, fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER, command=self._save
        ).grid(row=3, column=0, padx=26, pady=(12, 24), sticky="e")

    def _entry(self, master: object, label: str, row: int, placeholder: str) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=label, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12)).grid(
            row=row * 2, column=0, padx=18, pady=(12 if row == 0 else 0, 5), sticky="w"
        )
        entry = ctk.CTkEntry(master, height=38, placeholder_text=placeholder, fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER)
        entry.grid(row=(row * 2) + 1, column=0, padx=18, pady=(0, 12), sticky="ew")
        return entry

    def _option(self, master: object, label: str, values: list[str], row: int) -> ctk.CTkOptionMenu:
        ctk.CTkLabel(master, text=label, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12)).grid(
            row=row * 2, column=0, padx=18, pady=(12 if row == 0 else 0, 5), sticky="w"
        )
        values = values or [""]
        option = ctk.CTkOptionMenu(
            master, values=values, fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT, button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT, dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL, dropdown_hover_color=Theme.PANEL_ALT,
        )
        option.set(values[0])
        option.grid(row=(row * 2) + 1, column=0, padx=18, pady=(0, 12), sticky="ew")
        return option

    def _save(self) -> None:
        try:
            self._controller.create_request(
                self.item_entry.get(), self.quantity_entry.get(), self.requested_by_entry.get(),
                self.department_entry.get(), self.notes_entry.get("1.0", "end").strip(),
                bool(self.requires_director.get())
            )
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return
        self._on_saved()
        self.destroy()
