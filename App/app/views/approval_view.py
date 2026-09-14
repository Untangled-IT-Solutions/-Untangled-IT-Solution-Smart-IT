"""Approval workflow workspace view."""

from collections.abc import Callable

import customtkinter as ctk

from app.controllers.approval_controller import ApprovalController
from app.models.approval import ApprovalRequest
from app.utils.theme import Theme
from app.widgets.approval_card import ApprovalCard
from app.utils.async_tasks import run_in_background


class ApprovalView(ctk.CTkFrame):
    """Lists approval requests and exposes the staged review workflow."""

    def __init__(
        self,
        master: object,
        controller: ApprovalController,
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
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Approvals", text_color=Theme.TEXT, font=("Segoe UI", 30, "bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header, text="New Request", height=40, fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER, command=self._open_request_form
        ).grid(row=0, column=1, sticky="e")
        filters = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        filters.grid(row=1, column=0, pady=(20, 18), sticky="ew")
        ctk.CTkLabel(
            filters, text="Status", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12)
        ).pack(side="left", padx=(16, 8), pady=12)
        self.status_filter = ctk.CTkOptionMenu(
            filters, values=["All", "Pending", "Approved", "Rejected"],
            fg_color=Theme.PANEL_ALT, button_color=Theme.ACCENT, button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT, dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL, dropdown_hover_color=Theme.PANEL_ALT,
            command=lambda _value: self.refresh()
        )
        self.status_filter.set("All")
        self.status_filter.pack(side="left", padx=(0, 16), pady=12)
        self._list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self._list_frame.grid(row=2, column=0, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

    def _apply_initial_filters(self) -> None:
        status = self._initial_filters.get("status")
        if isinstance(status, str) and status in self.status_filter.cget("values"):
            self.status_filter.set(status)

    def refresh(self) -> None:
        status = self.status_filter.get()

        def fetch():
            return self._controller.get_approvals(status)

        def apply(requests):
            for child in self._list_frame.winfo_children():
                child.destroy()
            requests = requests or []
            if not requests:
                ctk.CTkLabel(
                    self._list_frame, text="No approval requests found.", text_color=Theme.MUTED_TEXT,
                    font=("Segoe UI", 14)
                ).grid(row=0, column=0, sticky="w")
                return
            for row, request in enumerate(requests):
                ApprovalCard(self._list_frame, request, self._open_review).grid(
                    row=row, column=0, sticky="ew", pady=(0, 12)
                )

        def failed(exc):
            print(f"⚠️ approvals refresh failed: {exc}")
            for child in self._list_frame.winfo_children():
                child.destroy()
            ctk.CTkLabel(
                self._list_frame, text="Could not load approvals.", text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 14)
            ).grid(row=0, column=0, sticky="w")

        run_in_background(self, fetch, apply, failed, name="approvals-loader")

    def _open_request_form(self) -> None:
        ApprovalRequestModal(self, self._controller, self.refresh)

    def _open_review(self, approval_id: int) -> None:
        request = next(
            (item for item in self._controller.get_approvals() if item.id == approval_id), None
        )
        if request is not None:
            ApprovalReviewModal(self, self._controller, request, self.refresh)


class ApprovalRequestModal(ctk.CTkToplevel):
    """Form for a new approval request."""

    def __init__(self, master: object, controller: ApprovalController, on_saved: Callable[[], None]) -> None:
        super().__init__(master)
        self._controller = controller
        self._on_saved = on_saved
        self.title("New Approval Request")
        self.geometry("560x670")
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self, text="New Approval Request", text_color=Theme.TEXT, font=("Segoe UI", 24, "bold")
        ).grid(row=0, column=0, padx=26, pady=(24, 10), sticky="w")
        form = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        form.grid(row=1, column=0, padx=26, sticky="ew")
        form.grid_columnconfigure(0, weight=1)
        self.title_entry = self._entry(form, "Request Title", 0)
        self.type_entry = self._option(form, "Approval Type", self._controller.get_request_types(), 1)
        self.requested_by_entry = self._option(form, "Requested By", self._controller.get_people_names(), 2)
        self.department_entry = self._option(form, "Department", self._controller.get_departments(), 3)
        self.amount_entry = self._entry(form, "Amount", 4, "0")
        self.description_entry = ctk.CTkTextbox(form, height=78, fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER, border_width=1)
        ctk.CTkLabel(form, text="Description", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12)).grid(
            row=10, column=0, padx=18, pady=(0, 5), sticky="w"
        )
        self.description_entry.grid(row=11, column=0, padx=18, pady=(0, 12), sticky="ew")
        self.requires_director = ctk.CTkCheckBox(
            form, text="Director approval required", text_color=Theme.TEXT
        )
        self.requires_director.grid(row=12, column=0, padx=18, pady=(0, 14), sticky="w")
        self.error_label = ctk.CTkLabel(self, text="", text_color=Theme.DANGER, font=("Segoe UI", 12))
        self.error_label.grid(row=2, column=0, padx=26, pady=(8, 0), sticky="w")
        ctk.CTkButton(
            self, text="Submit", height=40, fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER,
            command=self._save
        ).grid(row=3, column=0, padx=26, pady=(12, 24), sticky="e")

    def _entry(self, master: object, label: str, row: int, placeholder: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=label, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12)).grid(
            row=row * 2, column=0, padx=18, pady=(12 if row == 0 else 0, 5), sticky="w"
        )
        entry = ctk.CTkEntry(master, height=38, placeholder_text=placeholder or label, fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER)
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
                self.title_entry.get(), self.type_entry.get(), self.description_entry.get("1.0", "end").strip(),
                self.requested_by_entry.get(), self.department_entry.get(), self.amount_entry.get(),
                bool(self.requires_director.get())
            )
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return
        self._on_saved()
        self.destroy()


class ApprovalReviewModal(ctk.CTkToplevel):
    """Review screen that enforces the current stage in the approval chain."""

    def __init__(
        self, master: object, controller: ApprovalController, request: ApprovalRequest, on_updated: Callable[[], None]
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._request = request
        self._on_updated = on_updated
        self.title("Approval Review")
        self.geometry("560x550")
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        panel = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        panel.grid(row=0, column=0, padx=26, pady=26, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text=self._request.title, text_color=Theme.TEXT, font=("Segoe UI", 21, "bold"), wraplength=470, justify="left").grid(
            row=0, column=0, padx=20, pady=(20, 6), sticky="w"
        )
        details = f"{self._request.request_type} | {self._request.department}\nRequested by: {self._request.requested_by}\nAmount: {self._request.amount:.2f}\nStatus: {self._request.status}\nCurrent stage: {self._request.current_stage}\n\n{self._request.description}"
        ctk.CTkLabel(panel, text=details, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 13), justify="left", wraplength=470).grid(
            row=1, column=0, padx=20, pady=(0, 14), sticky="w"
        )
        self.reviewer_entry = ctk.CTkEntry(panel, height=38, placeholder_text="Reviewer name", fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER)
        self.reviewer_entry.insert(0, self._request.current_stage)
        self.reviewer_entry.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.reason_entry = ctk.CTkTextbox(panel, height=62, fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER, border_width=1)
        self.reason_entry.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.error_label = ctk.CTkLabel(panel, text="", text_color=Theme.DANGER, font=("Segoe UI", 12))
        self.error_label.grid(row=4, column=0, padx=20, sticky="w")
        if self._request.status == "Pending":
            buttons = ctk.CTkFrame(panel, fg_color="transparent")
            buttons.grid(row=5, column=0, padx=20, pady=(10, 20), sticky="ew")
            buttons.grid_columnconfigure((0, 1), weight=1)
            ctk.CTkButton(buttons, text=f"Approve as {self._request.current_stage}", fg_color=Theme.SUCCESS, hover_color=Theme.SUCCESS_HOVER, command=self._approve).grid(row=0, column=0, padx=(0, 5), sticky="ew")
            ctk.CTkButton(buttons, text="Reject", fg_color=Theme.DANGER, hover_color=Theme.DANGER_HOVER, command=self._reject).grid(row=0, column=1, padx=(5, 0), sticky="ew")

    def _approve(self) -> None:
        self._run_review(False)

    def _reject(self) -> None:
        self._run_review(True)

    def _run_review(self, rejected: bool) -> None:
        if self._request.id is None:
            return
        try:
            if rejected:
                self._controller.reject(
                    self._request.id, self.reviewer_entry.get(), self._request.current_stage,
                    self.reason_entry.get("1.0", "end").strip()
                )
            else:
                self._controller.approve(self._request.id, self.reviewer_entry.get(), self._request.current_stage)
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return
        self._on_updated()
        self.destroy()
