"""Calendar workspace view."""

import calendar
from collections import defaultdict
from datetime import date

import customtkinter as ctk

from app.controllers.calendar_controller import CalendarController
from app.models.calendar_event import CalendarEvent
from app.utils.theme import Theme


class CalendarView(ctk.CTkFrame):
    """Shows a non-duplicated monthly calendar generated from Work and database events."""

    def __init__(
        self,
        master: object,
        controller: CalendarController,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._initial_filters = filters or {}
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._calendar_frame: ctk.CTkFrame | None = None
        self._event_list: ctk.CTkScrollableFrame | None = None
        self._selected_day: str | None = None
        self._build_layout()
        self._apply_initial_filters()
        self.refresh()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header, text="Calendar", text_color=Theme.TEXT, font=("Segoe UI", 30, "bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header, text="Today", width=72, height=34, fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER, text_color=Theme.TEXT, command=self._go_today
        ).grid(row=0, column=1, padx=(0, 8), sticky="e")
        ctk.CTkButton(
            header, text="<", width=38, height=34, fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER, text_color=Theme.TEXT, command=lambda: self._change_month(-1)
        ).grid(row=0, column=2, padx=(0, 8))
        self.month_label = ctk.CTkLabel(header, text="", text_color=Theme.TEXT, font=("Segoe UI", 17, "bold"))
        self.month_label.grid(row=0, column=3, padx=(0, 8))
        ctk.CTkButton(
            header, text=">", width=38, height=34, fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER, text_color=Theme.TEXT, command=lambda: self._change_month(1)
        ).grid(row=0, column=4, padx=(0, 8))
        ctk.CTkButton(
            header, text="Show All", width=86, height=34, fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER, text_color=Theme.TEXT, command=self._show_all
        ).grid(row=0, column=5, padx=(0, 8))
        ctk.CTkButton(
            header, text="Add Event", width=96, height=34, fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER, command=self._open_event_form
        ).grid(row=0, column=6)
        ctk.CTkLabel(
            self,
            text="Operational schedule",
            text_color=Theme.MUTED_TEXT, font=("Segoe UI", 14)
        ).grid(row=1, column=0, pady=(6, 10), sticky="w")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self._calendar_frame = ctk.CTkFrame(body, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        self._calendar_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self._event_list = ctk.CTkScrollableFrame(
            body, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS
        )
        self._event_list.grid(row=0, column=1, sticky="nsew")
        self._event_list.grid_columnconfigure(0, weight=1)

    def _apply_initial_filters(self) -> None:
        if self._initial_filters.get("range") == "Upcoming":
            self._selected_day = None

    def refresh(self) -> None:
        """Render a month from database-backed Work-derived events."""
        self.month_label.configure(text=f"{calendar.month_name[self._month]} {self._year}")
        events = self._controller.get_month_events(self._year, self._month)
        self._render_calendar(events)
        self._render_events(events)

    def _render_calendar(self, events: list[CalendarEvent]) -> None:
        for child in self._calendar_frame.winfo_children():
            child.destroy()
        for column, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            ctk.CTkLabel(
                self._calendar_frame, text=name, text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 12, "bold")
            ).grid(row=0, column=column, padx=3, pady=(8, 5), sticky="ew")
            self._calendar_frame.grid_columnconfigure(column, weight=1, uniform="calendar_day")
        events_by_day: dict[str, list[CalendarEvent]] = defaultdict(list)
        for event in events:
            events_by_day[event.start_date].append(event)
        for row, week in enumerate(calendar.monthcalendar(self._year, self._month), start=1):
            self._calendar_frame.grid_rowconfigure(row, weight=1, minsize=76)
            for column, day in enumerate(week):
                date_key = date(self._year, self._month, day).isoformat() if day else ""
                cell_color = Theme.ACCENT if date_key and date_key == self._selected_day else Theme.PANEL_ALT
                cell = ctk.CTkFrame(self._calendar_frame, fg_color=cell_color, corner_radius=Theme.RADIUS)
                cell.grid(row=row, column=column, padx=2, pady=2, sticky="nsew")
                if not day:
                    continue
                self._bind_day(cell, date_key)
                ctk.CTkLabel(
                    cell, text=str(day), text_color=Theme.TEXT, font=("Segoe UI", 12, "bold")
                ).pack(anchor="w", padx=7, pady=(5, 3))
                for child in cell.winfo_children():
                    self._bind_day(child, date_key)
                for event in events_by_day[date_key][:2]:
                    event_label = ctk.CTkLabel(
                        cell, text=event.title, text_color=Theme.TEXT, fg_color=self._event_color(event.event_type),
                        corner_radius=4, font=("Segoe UI", 10), anchor="w", wraplength=86
                    )
                    event_label.pack(fill="x", padx=5, pady=(0, 2))
                    self._bind_day(event_label, date_key)
                if len(events_by_day[date_key]) > 2:
                    more_label = ctk.CTkLabel(
                        cell, text=f"+{len(events_by_day[date_key]) - 2} more", text_color=Theme.MUTED_TEXT,
                        font=("Segoe UI", 10)
                    )
                    more_label.pack(anchor="w", padx=7)
                    self._bind_day(more_label, date_key)

    def _render_events(self, events: list[CalendarEvent]) -> None:
        for child in self._event_list.winfo_children():
            child.destroy()
        visible_events = [
            event for event in events
            if self._selected_day is None or event.start_date == self._selected_day
        ]
        title = self._selected_day or "This Month"
        ctk.CTkLabel(
            self._event_list, text=title, text_color=Theme.TEXT, font=("Segoe UI", 16, "bold")
        ).grid(row=0, column=0, padx=16, pady=(16, 12), sticky="w")
        if not visible_events:
            ctk.CTkLabel(
                self._event_list, text="No scheduled events.", text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 13), wraplength=220, justify="left"
            ).grid(row=1, column=0, padx=16, pady=(0, 16), sticky="w")
            return
        for row, event in enumerate(visible_events, start=1):
            card = ctk.CTkFrame(self._event_list, fg_color=Theme.PANEL_ALT, corner_radius=Theme.RADIUS)
            card.grid(row=row, column=0, padx=12, pady=(0, 10), sticky="ew")
            ctk.CTkLabel(
                card, text=event.start_date, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 11)
            ).pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                card, text=event.title, text_color=Theme.TEXT, font=("Segoe UI", 13, "bold"),
                wraplength=210, justify="left"
            ).pack(anchor="w", padx=12)
            ctk.CTkLabel(
                card, text=f"{event.event_type} | {event.source_type}", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 11)
            ).pack(anchor="w", padx=12, pady=(2, 10))
            if event.source_type == "Manual" and event.id is not None:
                actions = ctk.CTkFrame(card, fg_color="transparent")
                actions.pack(fill="x", padx=12, pady=(0, 10))
                ctk.CTkButton(
                    actions, text="Edit", width=70, height=28, fg_color=Theme.ACCENT,
                    hover_color=Theme.ACCENT_HOVER,
                    command=lambda selected=event: self._open_event_form(selected)
                ).pack(side="left", padx=(0, 6))
                ctk.CTkButton(
                    actions, text="Delete", width=70, height=28, fg_color=Theme.DANGER,
                    hover_color=Theme.DANGER,
                    command=lambda selected=event: self._delete_event(selected)
                ).pack(side="left")

    def _change_month(self, offset: int) -> None:
        month = self._month + offset
        if month == 0:
            self._year -= 1
            month = 12
        elif month == 13:
            self._year += 1
            month = 1
        self._month = month
        self._selected_day = None
        self.refresh()

    def _go_today(self) -> None:
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._selected_day = today.isoformat()
        self.refresh()

    def _show_all(self) -> None:
        self._selected_day = None
        self.refresh()

    def _select_day(self, selected_day: str) -> None:
        self._selected_day = selected_day
        self.refresh()

    def _bind_day(self, widget: object, selected_day: str) -> None:
        if isinstance(widget, ctk.CTkBaseClass):
            widget.bind("<Button-1>", lambda _event: self._select_day(selected_day))

    def _open_event_form(self, event: CalendarEvent | None = None) -> None:
        for child in self._event_list.winfo_children():
            child.destroy()
        CalendarEventForm(
            self._event_list,
            self._controller,
            self.refresh,
            event,
        ).grid(row=0, column=0, padx=12, pady=12, sticky="ew")

    def _delete_event(self, event: CalendarEvent) -> None:
        if event.id is None:
            return
        self._controller.delete_event(event.id)
        self.refresh()

    @staticmethod
    def _event_color(event_type: str) -> str:
        return {
            "RFQ Deadline": Theme.PURPLE, "Supplier Deadline": Theme.WARNING,
            "Technical Visit": Theme.INFO, "Software Milestone": Theme.SUCCESS,
            "Training": Theme.ACCENT,
            "Meeting": Theme.ACCENT, "Leave": Theme.WARNING,
            "Birthday": Theme.PURPLE, "Project": Theme.SUCCESS,
            "Company Event": Theme.ACCENT, "Approval Deadline": Theme.DANGER,
        }.get(event_type, Theme.ACCENT)


class CalendarEventForm(ctk.CTkFrame):
    """Inline form for creating and editing manual calendar events."""

    def __init__(
        self,
        master: object,
        controller: CalendarController,
        on_saved: object,
        event: CalendarEvent | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.PANEL_ALT, corner_radius=Theme.RADIUS)
        self._controller = controller
        self._on_saved = on_saved
        self._event = event
        self.grid_columnconfigure(0, weight=1)
        self._build_form()

    def _build_form(self) -> None:
        heading = "Edit Event" if self._event else "Add Event"
        ctk.CTkLabel(self, text=heading, text_color=Theme.TEXT, font=Theme.FONT_HEADING).grid(
            row=0, column=0, padx=16, pady=(16, 12), sticky="w"
        )
        form = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        form.grid(row=1, column=0, padx=0, pady=(0, 10), sticky="ew")
        form.grid_columnconfigure(0, weight=1)
        self.title_entry = self._entry(form, "Title", self._event.title if self._event else "", 0)
        self.type_menu = self._menu(form, "Type", self._controller.get_event_types(), self._event.event_type if self._event else "Meeting", 1)
        self.start_entry = self._entry(form, "Start date (YYYY-MM-DD)", self._event.start_date if self._event else date.today().isoformat(), 2)
        self.end_entry = self._entry(form, "End date", self._event.end_date if self._event else "", 3)
        departments = ["General", *self._controller.get_departments()]
        self.department_menu = self._menu(form, "Department", departments, self._event.department if self._event else departments[0], 4)
        self.recurrence_menu = self._menu(
            form, "Recurrence", self._controller.get_recurrence_options(),
            self._event.recurrence if self._event else "None", 5
        )
        ctk.CTkLabel(form, text="Details", text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(
            row=6, column=0, padx=16, pady=(8, 4), sticky="w"
        )
        self.details_entry = ctk.CTkTextbox(
            form,
            height=84,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            text_color=Theme.TEXT,
        )
        self.details_entry.grid(row=7, column=0, padx=16, pady=(0, 16), sticky="ew")
        if self._event:
            self.details_entry.insert("1.0", self._event.details)
        self.error_label = ctk.CTkLabel(self, text="", text_color=Theme.DANGER, font=Theme.FONT_SMALL)
        self.error_label.grid(row=2, column=0, padx=16, sticky="w")
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, padx=16, pady=(10, 16), sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            actions, text="Cancel", height=38, fg_color=Theme.PANEL,
            hover_color=Theme.BORDER, text_color=Theme.TEXT, command=self._on_saved
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(
            actions, text="Save Event", height=38, fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER, command=self._save
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _entry(self, master: object, label: str, value: str, row: int) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=label, text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(
            row=row * 2, column=0, padx=16, pady=(12, 4), sticky="w"
        )
        entry = ctk.CTkEntry(
            master,
            height=38,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
            placeholder_text_color=Theme.MUTED_TEXT,
        )
        entry.grid(row=row * 2 + 1, column=0, padx=16, sticky="ew")
        entry.insert(0, value)
        return entry

    def _menu(self, master: object, label: str, values: list[str], value: str, row: int) -> ctk.CTkOptionMenu:
        ctk.CTkLabel(master, text=label, text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(
            row=row * 2, column=0, padx=16, pady=(12, 4), sticky="w"
        )
        menu = ctk.CTkOptionMenu(
            master,
            values=values,
            fg_color=Theme.PANEL,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
            dropdown_text_color=Theme.TEXT,
            dropdown_fg_color=Theme.PANEL,
            dropdown_hover_color=Theme.PANEL_ALT,
        )
        menu.grid(row=row * 2 + 1, column=0, padx=16, sticky="ew")
        menu.set(value if value in values else values[0])
        return menu

    def _save(self) -> None:
        try:
            values = (
                self.title_entry.get(),
                self.type_menu.get(),
                self.start_entry.get(),
                self.end_entry.get(),
                self.department_menu.get(),
                self.details_entry.get("1.0", "end").strip(),
                self.recurrence_menu.get(),
            )
            if self._event and self._event.id is not None:
                self._controller.update_event(self._event.id, *values)
            else:
                self._controller.create_event(*values)
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return
        self._on_saved()
