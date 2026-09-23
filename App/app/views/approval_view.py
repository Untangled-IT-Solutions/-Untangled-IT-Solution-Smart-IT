"""Approval workflow workspace view."""

from app.utils.ui_tasks import ui_task, ui_steps, RemoteCall, action_steps, ui_callback

from collections.abc import Callable

import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog

from app.controllers.approval_controller import ApprovalController
from app.models.approval import ApprovalRequest
from app.utils.theme import Theme
from app.widgets.approval_card import ApprovalCard


class ApprovalView(ctk.CTkFrame):
    """Lists approval requests and exposes the staged review workflow."""

    @ui_task
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
        (yield from ui_steps(self.refresh))

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
            header, text="Apply for Leave", height=40, fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER, command=self._open_leave_form
        ).grid(row=0, column=1, sticky="e", padx=(0, 10))
        ctk.CTkButton(
            header, text="New Request", height=40, fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER, command=self._open_request_form
        ).grid(row=0, column=2, sticky="e")
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

    @ui_task
    def refresh(self) -> None:
        for child in self._list_frame.winfo_children():
            child.destroy()
        requests = (yield RemoteCall(self._controller.get_approvals, self.status_filter.get()))
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

    def _open_request_form(self) -> None:
        ApprovalRequestModal(self, self._controller, self.refresh)

    def _open_leave_form(self) -> None:
        LeaveRequestModal(self, self._controller, self.refresh)

    @ui_task
    def _open_review(self, approval_id: int) -> None:
        request = next(
            (item for item in (yield RemoteCall(self._controller.get_approvals)) if item.id == approval_id), None
        )
        if request is not None:
            ApprovalReviewModal(self, self._controller, request, self.refresh)


class ApprovalRequestModal(ctk.CTkToplevel):
    """Form for a new approval request."""

    @ui_task
    def __init__(self, master: object, controller: ApprovalController, on_saved: Callable[[], None]) -> None:
        super().__init__(master)
        self._controller = controller
        self._on_saved = on_saved
        self.title("New Approval Request")
        self.geometry("560x670")
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        (yield from ui_steps(self._build_layout))

    @ui_task
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self, text="New Approval Request", text_color=Theme.TEXT, font=("Segoe UI", 24, "bold")
        ).grid(row=0, column=0, padx=26, pady=(24, 10), sticky="w")
        form = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        form.grid(row=1, column=0, padx=26, sticky="ew")
        form.grid_columnconfigure(0, weight=1)
        self.title_entry = self._entry(form, "Request Title", 0)
        self.type_entry = self._option(form, "Approval Type", (yield RemoteCall(self._controller.get_request_types)), 1)
        self.requested_by_entry = self._option(form, "Requested By", (yield RemoteCall(self._controller.get_people_names)), 2)
        self.department_entry = self._option(form, "Department", (yield RemoteCall(self._controller.get_departments)), 3)
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

    @ui_task
    def _save(self) -> None:
        try:
            (yield RemoteCall(self._controller.create_request, 
                self.title_entry.get(), self.type_entry.get(), self.description_entry.get("1.0", "end").strip(),
                self.requested_by_entry.get(), self.department_entry.get(), self.amount_entry.get(),
                bool(self.requires_director.get())
            ))
        except Exception as error:
            self.error_label.configure(text=str(error))
            return
        self._on_saved()
        self.destroy()


class LeaveRequestModal(ctk.CTkToplevel):
    """Dedicated dated leave request with authenticated document upload."""

    @ui_task
    def __init__(self, master, controller: ApprovalController, on_saved: Callable[[], None]) -> None:
        super().__init__(master)
        self._controller = controller
        self._on_saved = on_saved
        self._document_paths: list[str] = []
        self.title("Apply for Leave")
        self.geometry("600x650")
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        self._build_layout()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self, text="Apply for Leave", text_color=Theme.TEXT,
            font=("Segoe UI", 24, "bold"),
        ).grid(row=0, column=0, padx=26, pady=(24, 10), sticky="w")
        form = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        form.grid(row=1, column=0, padx=26, sticky="ew")
        form.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(form, text="Leave type", text_color=Theme.MUTED_TEXT).grid(row=0, column=0, padx=18, pady=(16, 5), sticky="w")
        self.leave_type = ctk.CTkOptionMenu(
            form,
            values=["Annual", "Sick", "Family Responsibility", "Unpaid", "Other"],
            fg_color=Theme.PANEL_ALT, button_color=Theme.ACCENT,
        )
        self.leave_type.set("Annual")
        self.leave_type.grid(row=1, column=0, columnspan=2, padx=18, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(form, text="Start date (YYYY-MM-DD)", text_color=Theme.MUTED_TEXT).grid(row=2, column=0, padx=(18, 8), sticky="w")
        ctk.CTkLabel(form, text="End date (YYYY-MM-DD)", text_color=Theme.MUTED_TEXT).grid(row=2, column=1, padx=(8, 18), sticky="w")
        self.start_date = ctk.CTkEntry(form, placeholder_text="2026-09-21", fg_color=Theme.PANEL_ALT)
        self.end_date = ctk.CTkEntry(form, placeholder_text="2026-09-22", fg_color=Theme.PANEL_ALT)
        self.start_date.grid(row=3, column=0, padx=(18, 8), pady=(5, 12), sticky="ew")
        self.end_date.grid(row=3, column=1, padx=(8, 18), pady=(5, 12), sticky="ew")

        ctk.CTkLabel(form, text="Reason", text_color=Theme.MUTED_TEXT).grid(row=4, column=0, padx=18, sticky="w")
        self.reason = ctk.CTkTextbox(form, height=90, fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER, border_width=1)
        self.reason.grid(row=5, column=0, columnspan=2, padx=18, pady=(5, 12), sticky="ew")

        self.document_label = ctk.CTkLabel(
            form, text="No supporting documents selected", text_color=Theme.MUTED_TEXT,
            anchor="w", wraplength=430,
        )
        self.document_label.grid(row=6, column=0, padx=18, pady=(2, 12), sticky="ew")
        ctk.CTkButton(
            form, text="Select documents…", command=self._pick_documents,
            fg_color=Theme.PANEL_ALT, text_color=Theme.TEXT,
        ).grid(row=6, column=1, padx=18, pady=(2, 12), sticky="e")
        ctk.CTkLabel(
            form,
            text="Sick leave requires a valid PDF, image, or DOCX doctor note.",
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 11),
        ).grid(row=7, column=0, columnspan=2, padx=18, sticky="w")
        self.requires_director = ctk.CTkCheckBox(
            form, text="Director approval required", text_color=Theme.TEXT,
        )
        self.requires_director.grid(row=8, column=0, columnspan=2, padx=18, pady=(14, 18), sticky="w")

        self.error_label = ctk.CTkLabel(self, text="", text_color=Theme.DANGER, wraplength=540)
        self.error_label.grid(row=2, column=0, padx=26, pady=(8, 0), sticky="w")
        self.save_button = ctk.CTkButton(
            self, text="Submit Leave Request", height=42, fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER, command=self._save,
        )
        self.save_button.grid(row=3, column=0, padx=26, pady=(12, 24), sticky="e")

    def _pick_documents(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Select supporting documents",
            filetypes=[
                ("Supported documents", "*.pdf *.png *.jpg *.jpeg *.docx"),
                ("All files", "*.*"),
            ],
        )
        selected = []
        for value in paths:
            path = Path(value)
            if path.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".docx"}:
                self.error_label.configure(text=f"Unsupported document type: {path.name}")
                continue
            if path.stat().st_size > 8 * 1024 * 1024:
                self.error_label.configure(text=f"{path.name} exceeds the 8 MB limit.")
                continue
            selected.append(str(path))
        self._document_paths = selected[:10]
        names = ", ".join(Path(value).name for value in self._document_paths)
        self.document_label.configure(text=names or "No supporting documents selected")

    @ui_task
    def _save(self) -> None:
        leave_type = self.leave_type.get()
        start = self.start_date.get().strip()
        end = self.end_date.get().strip()
        reason = self.reason.get("1.0", "end").strip()
        if not start or not end or not reason:
            self.error_label.configure(text="Start date, end date, and reason are required.")
            return
        if leave_type == "Sick" and not self._document_paths:
            self.error_label.configure(text="Attach a doctor note or medical certificate for sick leave.")
            return
        self.save_button.configure(state="disabled", text="Uploading and submitting…")
        try:
            yield RemoteCall(
                self._controller.submit_leave,
                leave_type, start, end, reason, list(self._document_paths),
                bool(self.requires_director.get()),
            )
        except Exception as error:
            self.error_label.configure(text=str(error))
            self.save_button.configure(state="normal", text="Submit Leave Request")
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
        leave_dates = ""
        if self._request.request_type == "Leave":
            leave_dates = f"\nLeave type: {self._request.leave_type}\nDates: {self._request.start_date} to {self._request.end_date}"
        details = f"{self._request.request_type} | {self._request.department}\nRequested by: {self._request.requested_by}{leave_dates}\nAmount: {self._request.amount:.2f}\nStatus: {self._request.status}\nCurrent stage: {self._request.current_stage}\n\n{self._request.description}"
        ctk.CTkLabel(panel, text=details, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 13), justify="left", wraplength=470).grid(
            row=1, column=0, padx=20, pady=(0, 14), sticky="w"
        )
        document_row = ctk.CTkFrame(panel, fg_color="transparent")
        document_row.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        if self._request.document_ids:
            ctk.CTkLabel(
                document_row, text="Supporting documents", text_color=Theme.MUTED_TEXT,
            ).pack(side="left")
            for index, document_id in enumerate(self._request.document_ids, start=1):
                ctk.CTkButton(
                    document_row,
                    text=f"Download {index}",
                    width=92,
                    fg_color=Theme.ACCENT,
                    command=lambda value=document_id: self._download_document(value),
                ).pack(side="right", padx=(5, 0))
        else:
            ctk.CTkLabel(
                document_row, text="No supporting documents", text_color=Theme.MUTED_TEXT,
            ).pack(side="left")
        self.reason_entry = ctk.CTkTextbox(panel, height=62, fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER, border_width=1)
        self.reason_entry.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.error_label = ctk.CTkLabel(panel, text="", text_color=Theme.DANGER, font=("Segoe UI", 12))
        self.error_label.grid(row=4, column=0, padx=20, sticky="w")
        if self._controller.can_review(self._request):
            buttons = ctk.CTkFrame(panel, fg_color="transparent")
            buttons.grid(row=5, column=0, padx=20, pady=(10, 20), sticky="ew")
            buttons.grid_columnconfigure((0, 1), weight=1)
            ctk.CTkButton(buttons, text=f"Approve as {self._request.current_stage}", fg_color=Theme.SUCCESS, hover_color=Theme.SUCCESS_HOVER, command=self._approve).grid(row=0, column=0, padx=(0, 5), sticky="ew")
            ctk.CTkButton(buttons, text="Reject", fg_color=Theme.DANGER, hover_color=Theme.DANGER_HOVER, command=self._reject).grid(row=0, column=1, padx=(5, 0), sticky="ew")

    @ui_task
    def _approve(self) -> None:
        (yield from ui_steps(self._run_review, False))

    @ui_task
    def _reject(self) -> None:
        (yield from ui_steps(self._run_review, True))

    @ui_task
    def _run_review(self, rejected: bool) -> None:
        if self._request.id is None:
            return
        try:
            if rejected:
                (yield RemoteCall(self._controller.reject, 
                    self._request.id, "", self._request.current_stage,
                    self.reason_entry.get("1.0", "end").strip()
                ))
            else:
                (yield RemoteCall(self._controller.approve, self._request.id, "", self._request.current_stage))
        except Exception as error:
            self.error_label.configure(text=str(error))
            return
        self._on_updated()
        self.destroy()

    @ui_task
    def _download_document(self, document_id: str) -> None:
        try:
            downloaded = yield RemoteCall(self._controller.download_document, document_id)
            name = Path(str(downloaded.get("name") or f"document-{document_id}")).name
            target = filedialog.asksaveasfilename(parent=self, initialfile=name)
            if not target:
                return
            Path(target).write_bytes(downloaded.get("content") or b"")
            self.error_label.configure(text=f"Saved securely to {target}", text_color=Theme.SUCCESS)
        except Exception as error:
            self.error_label.configure(text=str(error), text_color=Theme.DANGER)
