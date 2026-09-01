# app/views/quote_sync_view.py
"""Quote Sync View - Shows sync status and controls."""

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from typing import Dict, Any

from app.controllers.quote_sync_controller import QuoteSyncController
from app.utils.theme import Theme


class QuoteSyncView(ctk.CTkFrame):
    """View for managing quote synchronization between local and MongoDB."""

    def __init__(self, master, controller: QuoteSyncController):
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._setup_ui()
        self._update_status()

    def _setup_ui(self):
        """Setup the sync view UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        container.grid(row=0, column=0, padx=40, pady=40, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(
            container,
            text="🔄 Quote Synchronization",
            font=("Segoe UI", 24, "bold"),
            text_color=Theme.TEXT
        )
        title.grid(row=0, column=0, padx=30, pady=(30, 10), sticky="w")

        subtitle = ctk.CTkLabel(
            container,
            text="Sync quotes between the local database and MongoDB",
            font=("Segoe UI", 13),
            text_color=Theme.MUTED_TEXT
        )
        subtitle.grid(row=1, column=0, padx=30, pady=(0, 20), sticky="w")

        status_frame = ctk.CTkFrame(container, fg_color=Theme.PANEL_ALT, corner_radius=8)
        status_frame.grid(row=2, column=0, padx=30, pady=(0, 20), sticky="ew")
        status_frame.grid_columnconfigure(1, weight=1)

        conn_label = ctk.CTkLabel(
            status_frame,
            text="🔌 MongoDB Connection:",
            font=("Segoe UI", 13),
            text_color=Theme.TEXT
        )
        conn_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        self.conn_status = ctk.CTkLabel(
            status_frame,
            text="Checking...",
            font=("Segoe UI", 13, "bold"),
            text_color=Theme.TEXT
        )
        self.conn_status.grid(row=0, column=1, padx=20, pady=(20, 5), sticky="w")

        sync_label = ctk.CTkLabel(
            status_frame,
            text="📅 Last Sync:",
            font=("Segoe UI", 13),
            text_color=Theme.TEXT
        )
        sync_label.grid(row=1, column=0, padx=20, pady=(5, 20), sticky="w")

        self.sync_time = ctk.CTkLabel(
            status_frame,
            text="Never",
            font=("Segoe UI", 13),
            text_color=Theme.MUTED_TEXT
        )
        self.sync_time.grid(row=1, column=1, padx=20, pady=(5, 20), sticky="w")

        self.stats_frame = ctk.CTkFrame(container, fg_color=Theme.PANEL_ALT, corner_radius=8)
        self.stats_frame.grid(row=3, column=0, padx=30, pady=(0, 20), sticky="ew")
        self.stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stats_labels = {}
        stats_fields = [
            ("total", "📊 Total Quotes"),
            ("pending", "⏳ Pending"),
            ("in_review", "📝 In Review"),
            ("tasks", "✅ Tasks Created"),
        ]
        
        for idx, (key, label) in enumerate(stats_fields):
            frame = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
            frame.grid(row=0, column=idx, padx=10, pady=10, sticky="ew")
            
            ctk.CTkLabel(
                frame,
                text=label,
                text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 11),
            ).pack(anchor="w")
            
            self.stats_labels[key] = ctk.CTkLabel(
                frame,
                text="0",
                text_color=Theme.TEXT,
                font=("Segoe UI", 18, "bold"),
            )
            self.stats_labels[key].pack(anchor="w")

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=30, pady=(0, 30), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        pull_btn = ctk.CTkButton(
            btn_frame,
            text="⬇️ Pull from MongoDB",
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color="#2196F3",
            hover_color="#1976D2",
            command=self._pull_from_mongodb
        )
        pull_btn.grid(row=0, column=0, padx=10, sticky="ew")

        push_btn = ctk.CTkButton(
            btn_frame,
            text="⬆️ Push to MongoDB",
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color="#4CAF50",
            hover_color="#388E3C",
            command=self._push_to_mongodb
        )
        push_btn.grid(row=0, column=1, padx=10, sticky="ew")

        sync_all_btn = ctk.CTkButton(
            btn_frame,
            text="🔄 Sync All",
            height=45,
            font=("Segoe UI", 14, "bold"),
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._sync_all
        )
        sync_all_btn.grid(row=0, column=2, padx=10, sticky="ew")

        self.status_bar = ctk.CTkLabel(
            container,
            text="Ready",
            font=("Segoe UI", 12),
            text_color=Theme.MUTED_TEXT
        )
        self.status_bar.grid(row=5, column=0, padx=30, pady=(0, 20), sticky="w")

    def _update_status(self):
        if self._controller:
            connected = self._controller.is_mongodb_connected()
            if connected:
                self.conn_status.configure(text="✅ Connected", text_color="#4CAF50")
            else:
                self.conn_status.configure(text="❌ Disconnected", text_color="#F44336")
        self._update_stats()

    def _update_stats(self):
        if not self._controller:
            return
        try:
            status = self._controller.get_sync_status()
            stats = status.get("statistics", {})
            
            self.stats_labels["total"].configure(text=str(stats.get("total", 0)))
            by_status = stats.get("by_status", {})
            self.stats_labels["pending"].configure(text=str(by_status.get("Pending", 0)))
            self.stats_labels["in_review"].configure(text=str(by_status.get("In Review", 0)))
            self.stats_labels["tasks"].configure(text=str(stats.get("tasks_created", 0)))
            
        except Exception as e:
            print(f"Error updating stats: {e}")

    def _pull_from_mongodb(self):
        if not self._controller:
            messagebox.showerror("Error", "Quote Sync Controller not available")
            return
            
        self._set_status("⬇️ Pulling quotes from MongoDB...")
        result = self._controller.sync_quotes_from_mongodb()
        
        if result.get("success"):
            self._set_status(f"✅ {result.get('message', 'Sync complete')}")
            self.sync_time.configure(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self._update_stats()
            
            synced = result.get("synced", 0)
            updated = result.get("updated", 0)
            tasks = result.get("tasks_created", 0)
            duplicates = result.get("duplicates_skipped", 0)
            
            messagebox.showinfo(
                "Sync Complete", 
                f"Pull Results:\n"
                f"• New quotes: {synced}\n"
                f"• Updated quotes: {updated}\n"
                f"• Tasks created: {tasks}\n"
                f"• Duplicates skipped: {duplicates}\n\n"
                f"{result.get('message', '')}"
            )
        else:
            self._set_status(f"❌ Sync failed: {result.get('message', 'Unknown error')}")
            messagebox.showerror("Sync Failed", result.get("message", "Unknown error"))

    def _push_to_mongodb(self):
        if not self._controller:
            messagebox.showerror("Error", "Quote Sync Controller not available")
            return
            
        self._set_status("⬆️ Pushing quotes to MongoDB...")
        result = self._controller.sync_all_to_mongodb()
        
        if result.get("success"):
            self._set_status(f"✅ {result.get('message', 'Push complete')}")
            self.sync_time.configure(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self._update_stats()
            messagebox.showinfo("Sync Complete", result.get("message"))
        else:
            self._set_status(f"❌ Push failed: {result.get('message', 'Unknown error')}")
            messagebox.showerror("Sync Failed", result.get("message", "Unknown error"))

    def _sync_all(self):
        if not self._controller:
            messagebox.showerror("Error", "Quote Sync Controller not available")
            return
            
        self._set_status("🔄 Syncing all quotes...")
        self._pull_from_mongodb()
        self._update_stats()

    def _set_status(self, message: str):
        self.status_bar.configure(text=message)
        self.update_idletasks()