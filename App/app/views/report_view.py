"""Reports workspace view."""

import customtkinter as ctk

from app.controllers.report_controller import ReportController
from app.utils.theme import Theme
from app.utils.async_tasks import run_in_background


class ReportView(ctk.CTkFrame):
    """Previews and exports operational reports."""

    def __init__(
        self,
        master: object,
        controller: ReportController,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._initial_filters = filters or {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(header, text="Reports", text_color=Theme.TEXT, font=Theme.FONT_TITLE).grid(row=0, column=0, sticky="w")
        self.report_menu = ctk.CTkOptionMenu(
            header, values=self._controller.get_report_types(), fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT, button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT, dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL, dropdown_hover_color=Theme.PANEL_ALT,
            command=lambda _value: self.refresh(),
        )
        self.report_menu.grid(row=0, column=1, padx=12)
        self.export_menu = ctk.CTkOptionMenu(
            header, values=["PDF", "Excel", "CSV"], fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT, button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT, dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL, dropdown_hover_color=Theme.PANEL_ALT,
        )
        self.export_menu.grid(row=0, column=2, padx=(0, 12))
        ctk.CTkButton(header, text="Export", fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER, command=self._export).grid(row=0, column=3, sticky="w")
        self.status_label = ctk.CTkLabel(self, text="", text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL)
        self.status_label.grid(row=1, column=0, pady=(8, 12), sticky="w")
        self.preview_frame = ctk.CTkScrollableFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        self.preview_frame.grid(row=2, column=0, sticky="nsew")
        self._apply_initial_filters()
        self.refresh()

    def _apply_initial_filters(self) -> None:
        report_type = self._initial_filters.get("report_type")
        if isinstance(report_type, str) and report_type in self.report_menu.cget("values"):
            self.report_menu.set(report_type)

    def refresh(self) -> None:
        report_type = self.report_menu.get()

        def fetch():
            return self._controller.preview(report_type)

        def apply(rows):
            for child in self.preview_frame.winfo_children():
                child.destroy()
            rows = rows or []
            self.status_label.configure(text=f"{len(rows)} records ready")
            if not rows:
                ctk.CTkLabel(self.preview_frame, text="No records found.", text_color=Theme.MUTED_TEXT).grid(row=0, column=0, padx=16, pady=16, sticky="w")
                return
            headers = list(rows[0].keys())
            for column, header in enumerate(headers):
                self.preview_frame.grid_columnconfigure(column, weight=1)
                ctk.CTkLabel(self.preview_frame, text=header, text_color=Theme.TEXT, font=Theme.FONT_SMALL).grid(row=0, column=column, padx=10, pady=(12, 8), sticky="w")
            for row_index, row in enumerate(rows[:50], start=1):
                for column, header in enumerate(headers):
                    ctk.CTkLabel(self.preview_frame, text=str(row.get(header, "")), text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL, wraplength=180, justify="left").grid(row=row_index, column=column, padx=10, pady=5, sticky="w")

        def failed(exc):
            print(f"⚠️ report refresh failed: {exc}")
            for child in self.preview_frame.winfo_children():
                child.destroy()
            self.status_label.configure(text="Could not load report")
            ctk.CTkLabel(self.preview_frame, text="Could not load report.", text_color=Theme.MUTED_TEXT).grid(row=0, column=0, padx=16, pady=16, sticky="w")

        run_in_background(self, fetch, apply, failed, name="report-loader")

    def _export(self) -> None:
        path = self._controller.export(self.report_menu.get(), self.export_menu.get())
        self.status_label.configure(text=f"Exported {path}")
