# app/views/dashboard_view.py
"""Dashboard workspace view."""

import customtkinter as ctk
from typing import Optional

from app.controllers.dashboard_controller import DashboardController
from app.utils.theme import Theme
from app.widgets.summary_card import SummaryCard


class DashboardView(ctk.CTkFrame):
    """Main dashboard with metrics and activity feed."""

    def __init__(self, master, controller: DashboardController) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._refresh_job = None
        self._is_destroyed = False
        
        # Store grid configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Build UI
        self._build_layout()
        
        # Load data after UI is built
        self.after(100, self._safe_refresh)

    def _safe_refresh(self) -> None:
        """Safely refresh data if view still exists."""
        if not self._is_destroyed and self.winfo_exists():
            self._refresh_data()

    def _build_layout(self) -> None:
        """Build the dashboard layout."""
        # Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=28, pady=(20, 0), sticky="ew")
        title_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            title_frame,
            text="📊 Dashboard",
            text_color=Theme.TEXT,
            font=Theme.FONT_TITLE,
        ).grid(row=0, column=0, sticky="w")
        
        ctk.CTkLabel(
            title_frame,
            text="Operational overview and key metrics",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).grid(row=1, column=0, sticky="w")
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            title_frame,
            text="🔄 Refresh",
            width=100,
            height=32,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._safe_refresh,
        )
        refresh_btn.grid(row=0, column=1, rowspan=2, padx=(0, 0), sticky="e")

        # Metrics Grid
        self.metrics_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.metrics_frame.grid(row=1, column=0, padx=28, pady=(20, 0), sticky="ew")
        self.metrics_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        
        # Activity Feed
        activity_frame = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        activity_frame.grid(row=2, column=0, padx=28, pady=(20, 28), sticky="nsew")
        activity_frame.grid_columnconfigure(0, weight=1)
        activity_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(
            activity_frame,
            text="Recent Activity",
            text_color=Theme.TEXT,
            font=Theme.FONT_HEADING,
        ).grid(row=0, column=0, padx=20, pady=(16, 12), sticky="w")
        
        self.activity_list = ctk.CTkScrollableFrame(
            activity_frame,
            fg_color="transparent",
            scrollbar_button_color=Theme.PANEL_ALT,
            scrollbar_button_hover_color=Theme.BORDER,
        )
        self.activity_list.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        self.activity_list.grid_columnconfigure(0, weight=1)

    def _refresh_data(self) -> None:
        """Refresh dashboard data."""
        if self._is_destroyed or not self.winfo_exists():
            return
            
        try:
            summary = self._controller.get_summary()
            if not self._is_destroyed and self.winfo_exists():
                self._update_metrics(summary)
                self._update_activity(summary.latest_activity)
        except Exception as e:
            print(f"Error refreshing dashboard: {e}")

    def _update_metrics(self, summary) -> None:
        """Update metric cards."""
        if self._is_destroyed or not self.winfo_exists():
            return
            
        # Clear existing metrics
        for widget in self.metrics_frame.winfo_children():
            widget.destroy()
        
        metrics = [
            ("People Working", str(summary.people_working), Theme.SUCCESS, "👥"),
            ("On Leave", str(summary.people_on_leave), Theme.WARNING, "🌴"),
            ("Tasks Due Today", str(summary.tasks_due_today), Theme.DANGER, "⚠️"),
            ("Tasks Overdue", str(summary.tasks_overdue), Theme.DANGER, "🔥"),
            ("Pending Approvals", str(summary.pending_approvals), Theme.ACCENT, "📋"),
        ]
        
        for idx, (title, value, color, icon) in enumerate(metrics):
            card = SummaryCard(
                self.metrics_frame,
                title=title,
                value=value,
                accent_color=color,
                icon=icon,
            )
            card.grid(row=0, column=idx, padx=6, sticky="ew")

    def _update_activity(self, activities) -> None:
        """Update the activity feed."""
        if self._is_destroyed or not self.winfo_exists():
            return
            
        for widget in self.activity_list.winfo_children():
            widget.destroy()
        
        if not activities:
            ctk.CTkLabel(
                self.activity_list,
                text="No recent activity",
                text_color=Theme.MUTED_TEXT,
                font=Theme.FONT_BODY,
            ).pack(pady=20)
            return
        
        for activity in activities:
            item = ctk.CTkFrame(
                self.activity_list,
                fg_color="transparent",
                corner_radius=0,
            )
            item.pack(fill="x", pady=4)
            
            ctk.CTkLabel(
                item,
                text=f"{activity.category} • {activity.description}",
                text_color=Theme.TEXT,
                font=Theme.FONT_BODY,
                anchor="w",
            ).pack(side="left", padx=8)
            
            if activity.created_at:
                time_str = activity.created_at[:16] if len(activity.created_at) >= 16 else activity.created_at
                ctk.CTkLabel(
                    item,
                    text=time_str,
                    text_color=Theme.MUTED_TEXT,
                    font=Theme.FONT_SMALL,
                ).pack(side="right", padx=8)

    def destroy(self) -> None:
        """Clean up when view is destroyed."""
        self._is_destroyed = True
        if self._refresh_job:
            try:
                self.after_cancel(self._refresh_job)
            except:
                pass
        super().destroy()