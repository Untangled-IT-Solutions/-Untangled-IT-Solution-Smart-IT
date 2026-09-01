"""Global search dialog."""

import customtkinter as ctk

from app.controllers.search_controller import SearchController
from app.utils.theme import Theme


class GlobalSearchModal(ctk.CTkToplevel):
    """Searches SQLite-backed operational records from a single reusable dialog."""

    def __init__(self, master: object, controller: SearchController, query: str = "") -> None:
        super().__init__(master)
        self._controller = controller
        self.title("Global Search")
        self.geometry("700x620")
        self.minsize(600, 480)
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self._build_layout(query)
        self.search_entry.focus_set()
        if query.strip():
            self._search()

    def _build_layout(self, query: str) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(
            self, text="Global Search", text_color=Theme.TEXT, font=("Segoe UI", 25, "bold")
        ).grid(row=0, column=0, padx=26, pady=(24, 12), sticky="w")
        self.search_entry = ctk.CTkEntry(
            self, height=42, fg_color=Theme.PANEL_ALT, border_color=Theme.BORDER,
            placeholder_text="Search people, projects, work, RFQs, suppliers, or clients"
        )
        self.search_entry.insert(0, query)
        self.search_entry.grid(row=1, column=0, padx=26, sticky="ew")
        self.search_entry.bind("<Return>", lambda _event: self._search())
        self.results_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.results_frame.grid(row=2, column=0, padx=26, pady=(16, 24), sticky="nsew")
        self.results_frame.grid_columnconfigure(0, weight=1)

    def _search(self) -> None:
        for child in self.results_frame.winfo_children():
            child.destroy()
        results = self._controller.search(self.search_entry.get())
        if not results:
            ctk.CTkLabel(
                self.results_frame, text="No matching records.", text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 14)
            ).grid(row=0, column=0, sticky="w")
            return
        for row, result in enumerate(results):
            card = ctk.CTkFrame(
                self.results_frame, fg_color=Theme.PANEL, border_color=Theme.BORDER,
                border_width=1, corner_radius=Theme.RADIUS
            )
            card.grid(row=row, column=0, pady=(0, 10), sticky="ew")
            ctk.CTkLabel(
                card, text=result.source, text_color=Theme.ACCENT, font=("Segoe UI", 11, "bold")
            ).grid(row=0, column=0, padx=14, pady=(12, 2), sticky="w")
            ctk.CTkLabel(
                card, text=result.title, text_color=Theme.TEXT, font=("Segoe UI", 15, "bold")
            ).grid(row=1, column=0, padx=14, sticky="w")
            ctk.CTkLabel(
                card, text=result.detail, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12),
                wraplength=580, justify="left"
            ).grid(row=2, column=0, padx=14, pady=(3, 12), sticky="w")
