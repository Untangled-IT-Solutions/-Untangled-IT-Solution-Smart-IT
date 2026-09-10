"""Simple electronic leave and office request workspace."""

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk

from app.controllers.office_request_controller import OfficeRequestController
from app.utils.theme import Theme
from app.widgets.office_request_card import OfficeRequestCard

if TYPE_CHECKING:
    from app.models.account import UserAccount


class OfficeRequestView(ctk.CTkFrame):
    """Create leave, stationery, equipment, and general requests."""

    REQUEST_TYPES = (
        ("Leave Request", "Annual, sick or family responsibility leave", "#E8F4FF", "#1677D2"),
        ("Stationery & Office Supplies", "Paper, toner and daily consumables", "#FFF3DB", "#D97706"),
        ("Equipment", "Laptop, monitor and workplace equipment", "#EDE9FE", "#7C3AED"),
        ("Other", "Any operational request not listed above", "#E8F7EC", "#15803D"),
    )

    def __init__(
        self,
        master: object,
        controller: OfficeRequestController,
        current_account: "UserAccount | None" = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._account = current_account
        self._list_frame: ctk.CTkScrollableFrame | None = None
        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        title_group = ctk.CTkFrame(header, fg_color="transparent")
        title_group.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            title_group, text="REQUEST CENTRE", text_color=Theme.ACCENT,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_group, text="Leave and Office Requests", text_color=Theme.TEXT,
            font=("Segoe UI", 30, "bold"),
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            title_group,
            text="Submit a short electronic request and follow its approval status.",
            text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY,
        ).pack(anchor="w", pady=(4, 0))
        ctk.CTkButton(
            header, text="+  New Request", height=42, width=145,
            fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF", font=Theme.FONT_BUTTON,
            command=self._open_request_form,
        ).grid(row=0, column=1, sticky="e")

        choices = ctk.CTkFrame(self, fg_color="transparent")
        choices.grid(row=1, column=0, pady=(20, 16), sticky="ew")
        choices.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="request_type")
        for column, (name, description, background, color) in enumerate(self.REQUEST_TYPES):
            card = ctk.CTkFrame(
                choices, fg_color=Theme.PANEL, border_color=Theme.BORDER,
                border_width=1, corner_radius=14,
            )
            card.grid(
                row=0, column=column,
                padx=(0 if column == 0 else 5, 0 if column == 3 else 5),
                sticky="ew",
            )
            ctk.CTkLabel(
                card, text=str(column + 1), width=34, height=34,
                fg_color=background, text_color=color, corner_radius=11,
                font=("Segoe UI", 14, "bold"),
            ).pack(anchor="w", padx=14, pady=(13, 7))
            ctk.CTkLabel(
                card, text=name, text_color=Theme.TEXT,
                font=("Segoe UI", 13, "bold"), anchor="w", justify="left",
                wraplength=205,
            ).pack(anchor="w", padx=14)
            ctk.CTkLabel(
                card, text=description, text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 10), anchor="w", justify="left",
                wraplength=205,
            ).pack(anchor="w", padx=14, pady=(3, 13))

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            label_text="Submitted requests",
            label_text_color=Theme.TEXT,
            label_font=("Segoe UI", 17, "bold"),
        )
        self._list_frame.grid(row=2, column=0, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

    def refresh(self) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()
        requests = self._controller.get_requests()
        if not requests:
            empty = ctk.CTkFrame(
                self._list_frame, fg_color=Theme.PANEL,
                border_color=Theme.BORDER, border_width=1, corner_radius=14,
            )
            empty.grid(row=0, column=0, sticky="ew")
            ctk.CTkLabel(
                empty, text="No requests submitted yet", text_color=Theme.TEXT,
                font=("Segoe UI", 16, "bold"),
            ).pack(pady=(28, 5))
            ctk.CTkLabel(
                empty, text="Select New Request to apply for leave or request an office item.",
                text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY,
            ).pack(pady=(0, 28))
            return
        for row, request in enumerate(requests):
            OfficeRequestCard(self._list_frame, request).grid(
                row=row, column=0, pady=(0, 12), sticky="ew"
            )

    def _open_request_form(self) -> None:
        OfficeRequestModal(
            self, self._controller, self.refresh, current_account=self._account
        )


class OfficeRequestModal(ctk.CTkToplevel):
    """Short dynamic electronic request form."""

    LEAVE_TYPES = (
        "Annual / Vacation", "Sick / Medical",
        "Personal / Family Responsibility", "Other",
    )
    SUPPLY_ITEMS = (
        "Printer Paper", "Pens", "Files / Folders", "Dividers",
        "Printer Toner", "Stationery", "Coffee / Tea", "Sugar / Milk",
        "Water", "Cleaning Consumables", "Other",
    )
    EQUIPMENT_ITEMS = (
        "Laptop", "Desktop", "Monitor", "Keyboard", "Mouse",
        "Headset", "Ethernet Cable", "Printer", "Other",
    )

    def __init__(
        self,
        master: object,
        controller: OfficeRequestController,
        on_saved: Callable[[], None],
        current_account: "UserAccount | None" = None,
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._on_saved = on_saved
        self._account = current_account
        self.title("New Leave or Office Request")
        self.configure(fg_color=Theme.BG)
        self.transient(master.winfo_toplevel())
        self.grab_set()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(680, max(500, screen_width - 100))
        height = min(760, max(560, screen_height - 120))
        left = max(20, (screen_width - width) // 2)
        top = max(20, (screen_height - height) // 2 - 15)
        self.geometry(f"{width}x{height}+{left}+{top}")
        self.minsize(min(520, width), min(560, height))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_layout()

    def _build_layout(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=26, pady=(22, 12), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Submit a request", text_color=Theme.TEXT,
            font=("Segoe UI", 24, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Choose a request type. Only the necessary fields will appear.",
            text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY,
        ).grid(row=1, column=0, pady=(4, 0), sticky="w")
        ctk.CTkButton(
            header, text="Close", width=70, height=34, command=self.destroy,
            fg_color=Theme.PANEL_ALT, hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        self.form = ctk.CTkScrollableFrame(
            self, fg_color=Theme.PANEL, border_color=Theme.BORDER,
            border_width=1, corner_radius=14,
        )
        self.form.grid(row=1, column=0, padx=26, sticky="nsew")
        self.form.grid_columnconfigure(0, weight=1)
        self.request_type_var = ctk.StringVar(value="Leave Request")
        self._label(self.form, "What would you like to request?", 0)
        ctk.CTkComboBox(
            self.form, values=self._controller.get_request_types(),
            variable=self.request_type_var, state="readonly", height=42,
            command=self._request_type_changed,
            fg_color=Theme.BG, border_color=Theme.BORDER,
            button_color=Theme.ACCENT, button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        ).grid(row=1, column=0, padx=18, sticky="ew")

        people = self._controller.get_people_names()
        current_name = str(
            getattr(self._account, "full_name", "")
            or getattr(self._account, "username", "") or ""
        ).strip()
        if current_name and current_name not in people:
            people = [current_name, *people]
        people = people or [current_name or "Current employee"]
        self.requested_by_var = ctk.StringVar(value=current_name or people[0])
        self._label(self.form, "Requested by", 2)
        self._combo(self.form, self.requested_by_var, people, 3)

        departments = self._controller.get_departments()
        current_department = str(getattr(self._account, "department", "") or "").strip()
        if current_department and current_department not in departments:
            departments = [current_department, *departments]
        departments = departments or [current_department or "General"]
        self.department_var = ctk.StringVar(value=current_department or departments[0])
        self._label(self.form, "Department", 4)
        self._combo(self.form, self.department_var, departments, 5)
        self.dynamic = ctk.CTkFrame(self.form, fg_color="transparent")
        self.dynamic.grid(row=6, column=0, sticky="ew")
        self.dynamic.grid_columnconfigure(0, weight=1)
        self.error_label = ctk.CTkLabel(
            self.form, text="", text_color=Theme.DANGER,
            font=("Segoe UI", 12), anchor="w", justify="left",
        )
        self.error_label.grid(row=7, column=0, padx=18, pady=(5, 12), sticky="ew")
        self._build_dynamic_fields("Leave Request")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, padx=26, pady=(12, 20), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            footer, text="Your request will be sent for manager approval.",
            text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer, text="Submit Request", height=42, width=145,
            fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF", font=Theme.FONT_BUTTON,
            command=self._save,
        ).grid(row=0, column=1, sticky="e")

    def _request_type_changed(self, value: str) -> None:
        self.error_label.configure(text="")
        self._build_dynamic_fields(value)

    def _build_dynamic_fields(self, request_type: str) -> None:
        for child in self.dynamic.winfo_children():
            child.destroy()
        self.requires_director_var = ctk.BooleanVar(value=False)
        self.notes_box = None
        self.confirmation = None
        if request_type == "Leave Request":
            self.leave_type_var = ctk.StringVar(value=self.LEAVE_TYPES[0])
            self.start_date_var = ctk.StringVar()
            self.end_date_var = ctk.StringVar()
            self._label(self.dynamic, "Leave type", 0)
            self._combo(self.dynamic, self.leave_type_var, list(self.LEAVE_TYPES), 1)
            dates = ctk.CTkFrame(self.dynamic, fg_color="transparent")
            dates.grid(row=2, column=0, padx=18, pady=(12, 0), sticky="ew")
            dates.grid_columnconfigure((0, 1), weight=1)
            ctk.CTkLabel(dates, text="Start date (YYYY-MM-DD)", text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(dates, text="End date (YYYY-MM-DD)", text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(row=0, column=1, padx=(10, 0), sticky="w")
            self._date_entry(dates, self.start_date_var).grid(row=1, column=0, pady=(5, 0), sticky="ew")
            self._date_entry(dates, self.end_date_var).grid(row=1, column=1, padx=(10, 0), pady=(5, 0), sticky="ew")
            self._label(self.dynamic, "Short reason or note (optional)", 3)
            self.notes_box = ctk.CTkTextbox(
                self.dynamic, height=68, fg_color=Theme.BG,
                border_color=Theme.BORDER, border_width=1,
            )
            self.notes_box.grid(row=4, column=0, padx=18, pady=(0, 12), sticky="ew")
            self.confirmation = ctk.CTkCheckBox(
                self.dynamic,
                text="I confirm that the information is accurate and submit it for approval.",
                text_color=Theme.TEXT, checkbox_width=21, checkbox_height=21,
            )
            self.confirmation.grid(row=5, column=0, padx=18, pady=(2, 14), sticky="w")
            return

        self.item_var = ctk.StringVar()
        self.quantity_var = ctk.StringVar(value="1")
        if request_type == "Stationery & Office Supplies":
            values = list(self.SUPPLY_ITEMS)
            label = "Item needed"
        elif request_type == "Equipment":
            values = list(self.EQUIPMENT_ITEMS)
            label = "Equipment needed"
        else:
            values = [""]
            label = "Request title"
        self.item_var.set(values[0])
        self._label(self.dynamic, label, 0)
        ctk.CTkComboBox(
            self.dynamic, values=values, variable=self.item_var,
            state="normal", height=42, fg_color=Theme.BG,
            border_color=Theme.BORDER, button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER, text_color=Theme.TEXT,
        ).grid(row=1, column=0, padx=18, sticky="ew")
        if request_type != "Other":
            self._label(self.dynamic, "Quantity", 2)
            ctk.CTkEntry(
                self.dynamic, textvariable=self.quantity_var, height=42,
                fg_color=Theme.BG, border_color=Theme.BORDER,
                text_color=Theme.TEXT,
            ).grid(row=3, column=0, padx=18, sticky="ew")
            notes_row = 4
        else:
            notes_row = 2
        self._label(self.dynamic, "Request details (optional)", notes_row)
        self.notes_box = ctk.CTkTextbox(
            self.dynamic, height=76, fg_color=Theme.BG,
            border_color=Theme.BORDER, border_width=1,
        )
        self.notes_box.grid(row=notes_row + 1, column=0, padx=18, pady=(0, 12), sticky="ew")
        if request_type in {"Equipment", "Other"}:
            ctk.CTkCheckBox(
                self.dynamic, text="Director approval also required",
                variable=self.requires_director_var, text_color=Theme.TEXT,
            ).grid(row=notes_row + 2, column=0, padx=18, pady=(0, 14), sticky="w")

    def _save(self) -> None:
        self.error_label.configure(text="")
        request_type = self.request_type_var.get()
        requester = self.requested_by_var.get().strip()
        department = self.department_var.get().strip()
        if not requester or not department:
            self.error_label.configure(text="Requested by and Department are required.")
            return
        try:
            if request_type == "Leave Request":
                if self.confirmation is None or not self.confirmation.get():
                    raise ValueError("Please confirm that the leave information is accurate.")
                start_text = self.start_date_var.get().strip()
                end_text = self.end_date_var.get().strip()
                try:
                    start = datetime.strptime(start_text, "%Y-%m-%d").date()
                    end = datetime.strptime(end_text, "%Y-%m-%d").date()
                except ValueError as error:
                    raise ValueError("Enter the start and end dates as YYYY-MM-DD.") from error
                if end < start:
                    raise ValueError("End date cannot be before the start date.")
                days = (end - start).days + 1
                reason = self.notes_box.get("1.0", "end").strip() if self.notes_box else ""
                notes = (
                    f"Leave type: {self.leave_type_var.get()}\n"
                    f"Start date: {start_text}\nEnd date: {end_text}\n"
                    f"Total calendar days requested: {days}"
                )
                if reason:
                    notes += f"\nNote: {reason}"
                item = f"Leave Request - {self.leave_type_var.get()}"
                quantity = str(days)
                requires_director = False
            else:
                item = self.item_var.get().strip()
                quantity = "1" if request_type == "Other" else self.quantity_var.get().strip()
                notes = self.notes_box.get("1.0", "end").strip() if self.notes_box else ""
                requires_director = bool(self.requires_director_var.get())
            self._controller.create_request(
                item, quantity, requester, department, notes,
                requires_director, request_type,
            )
        except (ValueError, TypeError) as error:
            self.error_label.configure(text=str(error))
            return
        self._on_saved()
        self.destroy()

    @staticmethod
    def _label(master: object, text: str, row: int) -> None:
        ctk.CTkLabel(
            master, text=text, text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=row, column=0, padx=18, pady=(12, 5), sticky="w")

    @staticmethod
    def _combo(master: object, variable: ctk.StringVar, values: list[str], row: int) -> None:
        ctk.CTkComboBox(
            master, values=values, variable=variable, state="readonly",
            height=42, fg_color=Theme.BG, border_color=Theme.BORDER,
            button_color=Theme.ACCENT, button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        ).grid(row=row, column=0, padx=18, sticky="ew")

    @staticmethod
    def _date_entry(master: object, variable: ctk.StringVar) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            master, textvariable=variable, placeholder_text="2026-09-15",
            height=42, fg_color=Theme.BG, border_color=Theme.BORDER,
            text_color=Theme.TEXT,
        )
