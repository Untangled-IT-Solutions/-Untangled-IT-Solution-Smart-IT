"""Calendar workspace view."""

import calendar
from collections import defaultdict
from datetime import date
from datetime import datetime
import queue
import threading
from tkinter import messagebox

import customtkinter as ctk

from app.controllers.calendar_controller import CalendarController
from app.models.calendar_event import CalendarEvent
from app.services.meeting_assistant_service import MeetingAssistantService
from app.utils.theme import Theme


class CalendarView(ctk.CTkFrame):
    """Shows a non-duplicated monthly calendar generated from Work and database events."""

    CALENDAR_BLUE = "#4F7DF3"
    CALENDAR_BLUE_HOVER = "#3D68D6"

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
        self._event_dialog: CalendarEventDialog | None = None
        self._selected_day: str | None = None
        self._shown_reminders: set[str] = set()
        self._reminder_job = None
        self._build_layout()
        self._apply_initial_filters()
        self.refresh()
        self._reminder_job = self.after(30_000, self._check_reminders)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            header, text="Calendar", text_color=self.CALENDAR_BLUE, font=("Segoe UI", 30, "bold")
        ).grid(row=0, column=0, sticky="w")
        month_controls = ctk.CTkFrame(header, fg_color="transparent")
        month_controls.grid(row=0, column=1, sticky="e", padx=(10, 12))
        ctk.CTkButton(
            month_controls, text="‹", width=38, height=34, fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER, text_color=Theme.TEXT, command=lambda: self._change_month(-1)
        ).pack(side="left", padx=(0, 8))
        self.month_label = ctk.CTkLabel(month_controls, text="", text_color=Theme.TEXT, font=("Segoe UI", 17, "bold"), width=150)
        self.month_label.pack(side="left")
        ctk.CTkButton(
            month_controls, text="›", width=38, height=34, fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER, text_color=Theme.TEXT, command=lambda: self._change_month(1)
        ).pack(side="left", padx=(8, 0))
        ctk.CTkButton(
            header, text="+  Add Event", width=112, height=36, fg_color=self.CALENDAR_BLUE,
            hover_color=self.CALENDAR_BLUE_HOVER, command=self._open_event_form
        ).grid(row=0, column=2)

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, pady=(16, 10), sticky="ew")
        filters.grid_columnconfigure(0, weight=1)
        self.event_search = ctk.CTkEntry(
            filters,
            height=40,
            placeholder_text="Search events, departments, or details",
            fg_color="#E5E7EB",
            border_width=0,
            text_color="#243247",
            placeholder_text_color="#667085",
        )
        self.event_search.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.event_search.bind("<KeyRelease>", lambda _event: self.refresh())
        self.type_filter = ctk.CTkOptionMenu(
            filters,
            values=["All event types", *self._controller.get_event_types()],
            width=160,
            height=40,
            fg_color="#E5E7EB",
            button_color="#C7CDD6",
            button_hover_color="#AEB7C4",
            text_color="#243247",
            dropdown_fg_color=Theme.PANEL,
            dropdown_text_color=Theme.TEXT,
            command=lambda _value: self.refresh(),
        )
        self.type_filter.set("All event types")
        self.type_filter.grid(row=0, column=1, padx=(0, 10))
        ctk.CTkButton(
            filters,
            text="Clear",
            width=70,
            height=40,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.MUTED_TEXT,
            command=self._clear_filters,
        ).grid(row=0, column=2)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=4, minsize=600)
        body.grid_columnconfigure(1, weight=1, minsize=245)
        body.grid_rowconfigure(0, weight=1)
        self._calendar_frame = ctk.CTkFrame(body, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        self._calendar_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._event_list = ctk.CTkScrollableFrame(
            body, fg_color=Theme.PANEL, border_color=Theme.BORDER,
            border_width=1, corner_radius=Theme.RADIUS
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
        events = self._filter_events(events)
        self._render_calendar(events)
        self._render_events(events)

    def _check_reminders(self) -> None:
        """Show each due event reminder once while the app is open."""
        self._reminder_job = None
        if not self.winfo_exists():
            return
        now = datetime.now()
        try:
            events = self._controller.get_month_events(now.year, now.month)
            for event in events:
                if event.reminder_minutes < 0 or not event.start_time:
                    continue
                starts_at = self._event_start_datetime(event)
                if starts_at is None:
                    continue
                reminder_at = starts_at.timestamp() - (event.reminder_minutes * 60)
                key = f"{event.id}:{event.start_date}:{event.start_time}"
                if key not in self._shown_reminders and reminder_at <= now.timestamp() < starts_at.timestamp():
                    self._shown_reminders.add(key)
                    when = f" at {event.start_time}" if event.start_time else ""
                    messagebox.showinfo(
                        "Calendar reminder",
                        f"{event.title} starts{when}.\n\n"
                        f"{event.department or 'General'} · {event.location or 'No location added'}",
                        parent=self.winfo_toplevel(),
                    )
        finally:
            if self.winfo_exists():
                self._reminder_job = self.after(30_000, self._check_reminders)

    @staticmethod
    def _event_start_datetime(event: CalendarEvent) -> datetime | None:
        """Accept the friendly time formats shown by the event form."""
        time_text = event.start_time.strip().upper().replace("H", ":")
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I %p", "%Y-%m-%d %I:%M %p"):
            try:
                return datetime.strptime(f"{event.start_date} {time_text}", fmt)
            except ValueError:
                continue
        return None

    def _filter_events(self, events: list[CalendarEvent]) -> list[CalendarEvent]:
        query = self.event_search.get().strip().casefold()
        selected_type = self.type_filter.get()
        filtered = []
        for event in events:
            searchable = " ".join((event.title, event.department, event.details, event.event_type)).casefold()
            if query and query not in searchable:
                continue
            if selected_type != "All event types" and event.event_type != selected_type:
                continue
            filtered.append(event)
        return filtered

    def _clear_filters(self) -> None:
        self.event_search.delete(0, "end")
        self.type_filter.set("All event types")
        self.refresh()

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
            self._calendar_frame.grid_rowconfigure(row, weight=1, minsize=84)
            for column, day in enumerate(week):
                date_key = date(self._year, self._month, day).isoformat() if day else ""
                cell_color = Theme.BORDER if date_key and date_key == self._selected_day else Theme.PANEL_ALT
                cell = ctk.CTkFrame(self._calendar_frame, fg_color=cell_color, corner_radius=12)
                cell.grid(row=row, column=column, padx=2, pady=2, sticky="nsew")
                if not day:
                    continue
                self._bind_day(cell, date_key)
                is_selected = date_key == self._selected_day
                is_today = date_key == date.today().isoformat()
                ctk.CTkLabel(
                    cell,
                    text=str(day),
                    width=28 if is_selected or is_today else 0,
                    height=28 if is_selected or is_today else 0,
                    fg_color=self.CALENDAR_BLUE if is_selected else (Theme.DANGER if is_today else "transparent"),
                    corner_radius=14,
                    text_color="#FFFFFF" if is_selected or is_today else Theme.TEXT,
                    font=("Segoe UI", 12, "bold"),
                ).pack(anchor="w", padx=7, pady=(6, 4))
                for child in cell.winfo_children():
                    self._bind_day(child, date_key)
                for event in events_by_day[date_key][:2]:
                    event_label = ctk.CTkLabel(
                        cell, text=event.title, text_color="#334155", fg_color=self._event_color(event),
                        corner_radius=5, height=20, font=("Segoe UI", 10), anchor="w", wraplength=112
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
        today_key = date.today().isoformat()
        try:
            upcoming_events = self._filter_events(
                self._controller.get_upcoming_events(31)
            )
        except Exception:
            upcoming_events = events
        today_events = sorted(
            (event for event in upcoming_events if event.start_date == today_key),
            key=lambda event: (event.start_time or "99:99", event.title.casefold()),
        )
        ctk.CTkButton(
            self._event_list,
            text=f"Today  •  {date.today().strftime('%d %b')}",
            height=40, fg_color=self.CALENDAR_BLUE,
            hover_color=self.CALENDAR_BLUE_HOVER,
            font=("Segoe UI", 13, "bold"), command=self._go_today,
        ).grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
        ctk.CTkLabel(
            self._event_list, text="TODAY", text_color=self.CALENDAR_BLUE,
            font=("Segoe UI", 10, "bold"),
        ).grid(row=1, column=0, padx=14, pady=(4, 5), sticky="w")
        if today_events:
            for row, event in enumerate(today_events[:3], start=2):
                self._side_summary_card(event, row)
        else:
            ctk.CTkLabel(
                self._event_list, text="No events scheduled today.",
                text_color=Theme.MUTED_TEXT, font=("Segoe UI", 11),
            ).grid(row=2, column=0, padx=14, pady=(0, 10), sticky="w")

        next_row = 2 + max(1, min(len(today_events), 3))
        reminders = sorted(
            (
                event for event in upcoming_events
                if event.reminder_minutes >= 0 and event.start_date >= today_key
            ),
            key=lambda event: (event.start_date, event.start_time or "99:99"),
        )
        ctk.CTkLabel(
            self._event_list, text=f"REMINDERS  •  {len(reminders)}",
            text_color=Theme.SUCCESS, font=("Segoe UI", 10, "bold"),
        ).grid(row=next_row, column=0, padx=14, pady=(10, 5), sticky="w")
        next_row += 1
        if reminders:
            for event in reminders[:4]:
                self._side_summary_card(event, next_row, reminder=True)
                next_row += 1
        else:
            ctk.CTkLabel(
                self._event_list, text="No upcoming reminders.",
                text_color=Theme.MUTED_TEXT, font=("Segoe UI", 11),
            ).grid(row=next_row, column=0, padx=14, pady=(0, 10), sticky="w")
            next_row += 1

        visible_events = [
            event for event in events
            if self._selected_day is None or event.start_date == self._selected_day
        ]
        title = self._selected_day or "All Events This Month"
        ctk.CTkLabel(
            self._event_list, text=title, text_color=Theme.TEXT,
            font=("Segoe UI", 14, "bold"), wraplength=215, justify="left",
        ).grid(row=next_row, column=0, padx=14, pady=(12, 9), sticky="w")
        next_row += 1
        if not visible_events:
            ctk.CTkLabel(
                self._event_list, text="No scheduled events.", text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 13), wraplength=220, justify="left"
            ).grid(row=next_row, column=0, padx=14, pady=(0, 16), sticky="w")
            return
        for event in visible_events:
            self._side_event_card(event, next_row)
            next_row += 1

    def _side_summary_card(
        self, event: CalendarEvent, row: int, reminder: bool = False
    ) -> None:
        when = event.start_time or event.start_date
        if reminder:
            when = f"{event.start_date[5:]}  {event.start_time}".strip()
        card = ctk.CTkFrame(
            self._event_list, fg_color=self._event_color(event), corner_radius=6,
        )
        card.grid(row=row, column=0, padx=12, pady=(0, 6), sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text=event.title, text_color="#243247",
            font=("Segoe UI", 11, "bold"), justify="left",
            wraplength=205, anchor="w",
        ).grid(row=0, column=0, padx=9, pady=(7, 1), sticky="ew")
        ctk.CTkLabel(
            card, text=when, text_color="#475569", font=("Segoe UI", 10),
        ).grid(row=1, column=0, padx=9, pady=(0, 7), sticky="w")

    def _side_event_card(self, event: CalendarEvent, row: int) -> None:
        card = ctk.CTkFrame(
            self._event_list, fg_color=Theme.PANEL_ALT,
            border_color=self._event_color(event), border_width=2,
            corner_radius=Theme.RADIUS,
        )
        card.grid(row=row, column=0, padx=12, pady=(0, 9), sticky="ew")
        event_when = event.start_date + (f" at {event.start_time}" if event.start_time else "")
        ctk.CTkLabel(
            card, text=event_when, text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=11, pady=(9, 2))
        ctk.CTkLabel(
            card, text=event.title, text_color=Theme.TEXT,
            font=("Segoe UI", 12, "bold"), wraplength=205, justify="left",
        ).pack(anchor="w", padx=11)
        if event.location:
            ctk.CTkLabel(
                card, text=event.location, text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 10), wraplength=205, justify="left",
            ).pack(anchor="w", padx=11, pady=(3, 6))
        if event.source_type == "Manual" and event.id is not None:
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=11, pady=(7, 9))
            ctk.CTkButton(
                actions, text="Edit", width=64, height=27,
                fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER,
                command=lambda selected=event: self._open_event_form(selected),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                actions, text="Delete", width=64, height=27,
                fg_color=Theme.DANGER, hover_color=Theme.DANGER,
                command=lambda selected=event: self._delete_event(selected),
            ).pack(side="left")
        else:
            ctk.CTkLabel(
                card, text=event.source_type, text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 9),
            ).pack(anchor="w", padx=11, pady=(3, 9))

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
        if self._event_dialog is not None and self._event_dialog.winfo_exists():
            self._event_dialog.focus()
            return
        self._event_dialog = CalendarEventDialog(
            self.winfo_toplevel(),
            self._controller,
            event,
            self._selected_day or date.today().isoformat(),
            self._on_event_saved,
        )

    def _on_event_saved(self) -> None:
        self._event_dialog = None
        self.refresh()

    def _delete_event(self, event: CalendarEvent) -> None:
        if event.id is None:
            return
        self._controller.delete_event(event.id)
        self.refresh()

    @staticmethod
    def _event_color(event: CalendarEvent) -> str:
        """Return a distinct, stable pastel chip colour for each calendar event."""
        type_colours = {
            "RFQ Deadline": "#E9D5FF", "Supplier Deadline": "#FDE68A",
            "Technical Visit": "#BAE6FD", "Software Milestone": "#BBF7D0",
            "Meeting": "#C7D2FE", "Leave": "#FBCFE8",
            "Birthday": "#E9D5FF", "Project": "#A7F3D0",
            "Company Event": "#BAE6FD", "Approval Deadline": "#FECACA",
        }
        if event.event_type in type_colours:
            return type_colours[event.event_type]

        # Some operational entries, such as recurring training sessions, share
        # the same type. Rotate these through soft colours using stable event
        # data so adjacent events are visibly different without random flicker.
        palette = ("#BFDBFE", "#BBF7D0", "#FDE68A", "#FBCFE8", "#DDD6FE", "#BAE6FD")
        colour_key = f"{event.title}|{event.start_date}|{event.event_type}"
        return palette[sum(ord(character) for character in colour_key) % len(palette)]

    def destroy(self) -> None:
        if self._reminder_job is not None:
            try:
                self.after_cancel(self._reminder_job)
            except Exception:
                pass
        super().destroy()


class CalendarEventDialog(ctk.CTkToplevel):
    """Accessible pop-up form for creating and editing manual calendar events."""

    def __init__(
        self,
        master: object,
        controller: CalendarController,
        event: CalendarEvent | None = None,
        selected_date: str | None = None,
        on_saved: object | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.PANEL)
        self._controller = controller
        self._on_saved = on_saved
        self._event = event
        self._meeting_assistant = MeetingAssistantService()
        self._ai_processing = False
        self._ai_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._selected_date = selected_date or date.today().isoformat()
        self.title("Edit event" if event else "Add event")
        self.geometry("780x700")
        self.minsize(680, 600)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_form()
        self.after(50, self._centre_on_parent)

    def _build_form(self) -> None:
        heading = "Edit Event" if self._event else "Add Event"
        ctk.CTkLabel(self, text=heading, text_color=Theme.TEXT, font=Theme.FONT_HEADING).grid(
            row=0, column=0, padx=28, pady=(24, 4), sticky="w"
        )
        ctk.CTkLabel(
            self,
            text="Add the operational details below. All controls remain visible while you work.",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=0, column=0, padx=28, pady=(52, 12), sticky="w")
        form = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        form.grid(row=1, column=0, padx=28, pady=(8, 0), sticky="nsew")
        form.grid_columnconfigure((0, 1), weight=1)
        self.title_entry = self._entry(form, "Event title", self._event.title if self._event else "", 0, 0)
        self.type_menu = self._menu(form, "Event type", self._controller.get_event_types(), self._event.event_type if self._event else "Meeting", 0, 1)
        self.start_entry = self._entry(form, "Start date (YYYY-MM-DD)", self._event.start_date if self._event else self._selected_date, 1, 0)
        self.end_entry = self._entry(form, "End date (optional)", self._event.end_date if self._event else "", 1, 1)
        departments = ["General", *self._controller.get_departments()]
        self.department_menu = self._menu(form, "Department", departments, self._event.department if self._event else departments[0], 2, 0)
        self.recurrence_menu = self._menu(
            form, "Recurrence", self._controller.get_recurrence_options(),
            self._event.recurrence if self._event else "None", 2, 1
        )
        reminder_values = ["No in-app reminder", "At start", "5 minutes before", "10 minutes before", "15 minutes before", "30 minutes before", "1 hour before"]
        self.reminder_menu = self._menu(
            form, "In-app reminder", reminder_values,
            self._reminder_label(self._event.reminder_minutes if self._event else -1), 3, 0
        )
        self.start_time_entry = self._entry(
            form, "Start time (optional — e.g. 9h00 or 9 AM)",
            self._event.start_time if self._event else "", 3, 1
        )
        self.end_time_entry = self._entry(
            form, "End time (optional — any format)",
            self._event.end_time if self._event else "", 4, 0
        )
        self.location_entry = self._entry(
            form, "Location or meeting link (optional)",
            self._event.location if self._event else "", 4, 1
        )
        self.report_email_entry = self._entry(
            form, "Send written report to email(s) (optional)", "", 5, 0
        )
        self.attendees_entry = self._entry(
            form, "Attendees (names or email addresses)",
            self._event.attendees if self._event else "", 5, 1
        )
        self.details_entry = self._textbox(
            form, "Event details", self._event.details if self._event else "", 12, 82
        )
        self._build_ai_notes_panel(form, 14)
        self.error_label = ctk.CTkLabel(self, text="", text_color=Theme.DANGER, font=Theme.FONT_SMALL)
        self.error_label.grid(row=2, column=0, padx=28, pady=(8, 0), sticky="w")
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=3, column=0, padx=28, pady=(12, 24), sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            actions, text="Cancel", height=38, fg_color=Theme.PANEL,
            hover_color=Theme.BORDER, text_color=Theme.TEXT, command=self._close
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.save_button = ctk.CTkButton(
            actions, text="Save Event", height=38, fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER, command=self._save
        )
        self.save_button.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _entry(self, master: object, label: str, value: str, row: int, column: int) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=label, text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(
            row=row * 2, column=column, padx=(0, 12) if column == 0 else (12, 0), pady=(8, 4), sticky="w"
        )
        entry = ctk.CTkEntry(
            master,
            height=38,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
            placeholder_text_color=Theme.MUTED_TEXT,
        )
        entry.grid(row=row * 2 + 1, column=column, padx=(0, 12) if column == 0 else (12, 0), sticky="ew")
        entry.insert(0, value)
        return entry

    def _menu(self, master: object, label: str, values: list[str], value: str, row: int, column: int) -> ctk.CTkOptionMenu:
        ctk.CTkLabel(master, text=label, text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).grid(
            row=row * 2, column=column, padx=(0, 12) if column == 0 else (12, 0), pady=(8, 4), sticky="w"
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
        menu.grid(row=row * 2 + 1, column=column, padx=(0, 12) if column == 0 else (12, 0), sticky="ew")
        menu.set(value if value in values else values[0])
        return menu

    def _textbox(
        self, master: object, label: str, value: str, row: int, height: int
    ) -> ctk.CTkTextbox:
        ctk.CTkLabel(
            master, text=label, text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL
        ).grid(row=row, column=0, columnspan=2, pady=(10, 4), sticky="w")
        textbox = ctk.CTkTextbox(
            master, height=height, fg_color=Theme.PANEL,
            border_color=Theme.BORDER, border_width=1, text_color=Theme.TEXT,
        )
        textbox.grid(row=row + 1, column=0, columnspan=2, pady=(0, 4), sticky="ew")
        if value:
            textbox.insert("1.0", value)
        return textbox

    def _build_ai_notes_panel(self, master: object, row: int) -> None:
        panel = ctk.CTkFrame(master, fg_color=Theme.PANEL_ALT, corner_radius=Theme.RADIUS)
        panel.grid(row=row, column=0, columnspan=2, pady=(12, 14), sticky="ew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel, text="Written Meeting Report", text_color=Theme.TEXT,
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, padx=14, pady=(12, 2), sticky="w")
        ctk.CTkLabel(
            panel,
            text="Creates a transcript and Word summary. Microphone audio is not saved.",
            text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL,
        ).grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 8), sticky="w")
        self.recording_consent_var = ctk.BooleanVar(value=False)
        self.consent_checkbox = ctk.CTkCheckBox(
            panel,
            text="I confirm everyone has agreed to live transcription",
            variable=self.recording_consent_var,
            command=self._update_recording_controls,
            text_color=Theme.TEXT,
        )
        self.consent_checkbox.grid(row=2, column=0, padx=14, pady=(0, 10), sticky="w")
        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.grid(row=3, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")
        self.record_button = ctk.CTkButton(
            controls, text="Start transcription", width=138, height=34,
            fg_color=Theme.DANGER, hover_color=Theme.DANGER,
            command=self._start_recording, state="disabled",
        )
        self.record_button.pack(side="left", padx=(0, 8))
        self.stop_recording_button = ctk.CTkButton(
            controls, text="Stop & create report", width=158, height=34,
            fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER,
            command=self._stop_recording, state="disabled",
        )
        self.stop_recording_button.pack(side="left", padx=(0, 10))
        self.recording_status = ctk.CTkLabel(
            controls, text="Not transcribing", text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        )
        self.recording_status.pack(side="left")

    def _update_recording_controls(self) -> None:
        if self._meeting_assistant.is_recording or self._ai_processing:
            return
        state = "normal" if self.recording_consent_var.get() else "disabled"
        self.record_button.configure(state=state)

    def _start_recording(self) -> None:
        if not self.recording_consent_var.get():
            self.recording_status.configure(
                text="Participant consent is required.", text_color=Theme.DANGER
            )
            return
        try:
            self._meeting_assistant.start_recording()
        except RuntimeError as error:
            self.recording_status.configure(text=str(error), text_color=Theme.DANGER)
            return
        self.record_button.configure(state="disabled")
        self.stop_recording_button.configure(state="normal")
        self.save_button.configure(state="disabled")
        self.recording_status.configure(text="Transcribing meeting…", text_color=Theme.DANGER)

    def _stop_recording(self) -> None:
        if not self._meeting_assistant.is_recording or self._ai_processing:
            return
        self._ai_processing = True
        self.stop_recording_button.configure(state="disabled")
        self.recording_status.configure(text="Creating written report…", text_color=Theme.MUTED_TEXT)
        title = self.title_entry.get().strip() or "Untitled meeting"
        event_date = self.start_entry.get().strip()
        start_time = self.start_time_entry.get().strip()
        location = self.location_entry.get().strip()
        report_recipients = self.report_email_entry.get().strip()
        event_id = self._event.id if self._event else None

        def worker() -> None:
            try:
                result = self._meeting_assistant.stop_and_generate_report(
                    title, event_date, start_time, location
                )
                email_sent = False
                if report_recipients:
                    email_sent = self._controller.send_meeting_report(
                        report_recipients,
                        title,
                        result.summary,
                        result.report_path,
                        event_id,
                    )
                self._ai_queue.put(
                    ("success", (result, email_sent, bool(report_recipients)))
                )
            except Exception as error:
                self._ai_queue.put(("error", str(error)))

        threading.Thread(target=worker, name="meeting-notes-ai", daemon=True).start()
        self.after(100, self._poll_ai_result)

    def _poll_ai_result(self) -> None:
        if not self.winfo_exists():
            return
        try:
            status, value = self._ai_queue.get_nowait()
        except queue.Empty:
            if self._ai_processing:
                self.after(100, self._poll_ai_result)
            return
        if status == "success":
            result, email_sent, email_requested = value
            self._apply_generated_report(result, email_sent, email_requested)
        else:
            self._meeting_notes_failed(value)

    def _apply_generated_report(
        self, result: object, email_sent: bool, email_requested: bool
    ) -> None:
        if not self.winfo_exists():
            return
        existing = self.details_entry.get("1.0", "end").strip()
        summary = str(result.summary)
        combined = f"{existing}\n\nMeeting Summary:\n{summary}" if existing else summary
        self.details_entry.delete("1.0", "end")
        self.details_entry.insert("1.0", combined)
        self._ai_processing = False
        self.save_button.configure(state="normal")
        if email_sent:
            message = f"Report emailed: {result.report_path.name}"
            colour = Theme.SUCCESS
        elif email_requested:
            message = f"Report created, but email was not sent: {result.report_path.name}"
            colour = Theme.WARNING
        else:
            message = f"Report created: {result.report_path.name}"
            colour = Theme.SUCCESS
        self.recording_status.configure(text=message, text_color=colour)
        self._update_recording_controls()

    def _meeting_notes_failed(self, message: str) -> None:
        if not self.winfo_exists():
            return
        self._ai_processing = False
        self.save_button.configure(state="normal")
        self.recording_status.configure(text=message, text_color=Theme.DANGER)
        self._update_recording_controls()

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
                self._controller.update_event(
                    self._event.id, *values, **self._meeting_values()
                )
            else:
                self._controller.create_event(*values, **self._meeting_values())
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return
        if callable(self._on_saved):
            self._on_saved()
        self.destroy()

    def _meeting_values(self) -> dict[str, object]:
        existing = self._event
        return {
            "start_time": self.start_time_entry.get().strip(),
            "end_time": self.end_time_entry.get().strip(),
            "location": self.location_entry.get().strip(),
            "attendees": self.attendees_entry.get().strip(),
            "agenda": existing.agenda if existing else "",
            "minutes": existing.minutes if existing else "",
            "summary": existing.summary if existing else "",
            "decisions": existing.decisions if existing else "",
            "action_items": existing.action_items if existing else "",
            "reminder_minutes": self._reminder_minutes(self.reminder_menu.get()),
            "send_invites": False,
            "send_summary": False,
        }

    @staticmethod
    def _reminder_label(minutes: int) -> str:
        return {
            -1: "No in-app reminder", 0: "At start", 5: "5 minutes before",
            10: "10 minutes before", 15: "15 minutes before",
            30: "30 minutes before", 60: "1 hour before",
        }.get(minutes, "No in-app reminder")

    @staticmethod
    def _reminder_minutes(label: str) -> int:
        return {
            "No in-app reminder": -1, "At start": 0, "5 minutes before": 5,
            "10 minutes before": 10, "15 minutes before": 15,
            "30 minutes before": 30, "1 hour before": 60,
        }.get(label, -1)

    def _close(self) -> None:
        self._meeting_assistant.cancel_recording()
        if callable(self._on_saved):
            self._on_saved()
        self.destroy()

    def _centre_on_parent(self) -> None:
        self.update_idletasks()
        parent = self.master
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
