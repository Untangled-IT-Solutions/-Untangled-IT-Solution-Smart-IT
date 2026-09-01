# app/widgets/summary_card.py
"""Summary card widget for dashboard metrics."""

import customtkinter as ctk

from app.utils.theme import Theme


class SummaryCard(ctk.CTkFrame):
    """A card widget for displaying summary metrics."""

    def __init__(
        self,
        master,
        title: str,
        value: str,
        accent_color: str = Theme.ACCENT,
        icon: str = "",
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=Theme.PANEL,
            corner_radius=Theme.RADIUS,
            **kwargs
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Accent bar at top
        accent = ctk.CTkFrame(
            self,
            height=4,
            fg_color=accent_color,
            corner_radius=0,
        )
        accent.grid(row=0, column=0, padx=0, pady=0, sticky="ew")
        
        # Content frame
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, padx=16, pady=(12, 16), sticky="ew")
        content.grid_columnconfigure(1, weight=1)
        
        # Icon
        if icon:
            ctk.CTkLabel(
                content,
                text=icon,
                font=("Segoe UI", 28),
                text_color=Theme.TEXT,
            ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        
        # Value
        ctk.CTkLabel(
            content,
            text=value,
            font=("Segoe UI", 28, "bold"),
            text_color=Theme.TEXT,
        ).grid(row=0, column=1, sticky="e")
        
        # Title
        ctk.CTkLabel(
            content,
            text=title,
            font=("Segoe UI", 12),
            text_color=Theme.MUTED_TEXT,
        ).grid(row=1, column=1, sticky="e")