"""Global search modal stub."""

import customtkinter as ctk
from app.utils.theme import Theme


class GlobalSearchModal(ctk.CTkToplevel):
    def __init__(self, master, controller=None) -> None:
        super().__init__(master)
        self.title("Search")
        self.geometry("480x320")
        self.configure(fg_color=Theme.BG)
        ctk.CTkLabel(
            self,
            text="Global search will be available once the backend search endpoint is ready.",
            text_color=Theme.MUTED_TEXT,
            wraplength=400,
        ).pack(expand=True, padx=24, pady=24)
