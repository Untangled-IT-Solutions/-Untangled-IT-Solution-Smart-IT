"""Attendance timer widget – Backend API only, non-blocking."""

from __future__ import annotations

from typing import Any, Optional
import queue
import threading
from datetime import datetime, timezone

import customtkinter as ctk

from app.utils.theme import Theme


class TimerWidget(ctk.CTkFrame):
    """Local attendance clock backed by occasional authoritative API syncs."""

    REFRESH_SECONDS = 30

    def __init__(self, master, employee_name: str, employee_id,
                 mongo_attendance: Any,
                 mongo_auth: Any = None):
        super().__init__(master, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        self._mongo_attendance = mongo_attendance
        self._mongo_auth = mongo_auth
        self._employee_name = employee_name
        self._employee_id = employee_id
        self._update_job = None
        self._sync_job = None
        self._is_destroyed = False
        self._state = None
        self._navigation_controller = None  # Timer is intentionally not a navigation owner.
        self._busy = False
        self._backend_queue = queue.Queue()
        self._queue_job = None
        self._build_layout()
        # TimerWidget is a UI component, not the navigation owner.
        # NavigationController must be attached to MainWindow instead.
        self._queue_job = self.after(200, self._drain_backend_queue)
        self.after(100, self._initial_sync)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.status_label = ctk.CTkLabel(self, text="⏱️ Loading...", text_color=Theme.MUTED_TEXT,
                                         font=("Segoe UI", 14, "bold"))
        self.status_label.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        self.timer_display = ctk.CTkLabel(self, text="00:00:00", text_color=Theme.TEXT,
                                          font=("Segoe UI", 24, "bold"))
        self.timer_display.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=0, column=1, rowspan=2, padx=16, pady=8, sticky="e")
        self.clock_button = ctk.CTkButton(button_frame, text="Clock In", width=100, height=36,
                                          fg_color=Theme.SUCCESS, hover_color="#2E7D32",
                                          command=self._toggle_clock)
        self.clock_button.grid(row=0, column=0, pady=(0, 4))
        self.break_button = ctk.CTkButton(button_frame, text="Break", width=100, height=32,
                                          fg_color=Theme.WARNING, hover_color="#F57C00",
                                          command=self._toggle_break, state="disabled")
        self.break_button.grid(row=1, column=0)

    def _initial_sync(self) -> None:
        self._sync_from_backend()
        self._schedule_local_tick()

    def _run_backend(self, operation, on_success=None, action_name="attendance") -> None:
        """Run network I/O off the Tkinter thread and marshal the result back."""
        if self._is_destroyed or self._busy:
            return
        self._busy = True
        self._set_buttons_busy(True)

        import threading

        def worker():
            try:
                result = operation()
                self._backend_queue.put(("success", result, on_success, action_name))
            except Exception as exc:
                self._backend_queue.put(("error", exc, None, action_name))

        threading.Thread(target=worker, name="attendance-api", daemon=True).start()

    def _drain_backend_queue(self) -> None:
        """Apply background HTTP results on Tkinter's main thread only."""
        if self._is_destroyed:
            return

        handled = False
        try:
            while True:
                kind, payload, callback, action_name = self._backend_queue.get_nowait()
                handled = True
                if kind == "success":
                    self._backend_success(payload, callback)
                else:
                    self._backend_error(payload, action_name)
        except queue.Empty:
            pass
        except Exception as exc:
            print(f"⚠️ Attendance UI callback error: {exc}")

        if not self._is_destroyed:
            try:
                self._queue_job = self.after(25 if handled else 200, self._drain_backend_queue)
            except Exception:
                self._queue_job = None

    def _backend_success(self, result, callback=None) -> None:
        self._busy = False
        self._set_buttons_busy(False)
        if callback:
            callback(result)
        else:
            self._state = result
            self._render_state()

    def _backend_error(self, exc, action_name="attendance") -> None:
        self._busy = False
        self._set_buttons_busy(False)
        print(f"⚠️ {action_name} error: {exc}")
        # Keep the last known state visible; retry the authoritative sync later.
        self._sync_job = self.after(5000, self._sync_from_backend) if not self._is_destroyed else None

    def _set_buttons_busy(self, busy: bool) -> None:
        if self._is_destroyed:
            return
        try:
            self.clock_button.configure(state="disabled" if busy else "normal")
            if busy:
                self.break_button.configure(state="disabled")
            elif self._state:
                self._render_state()
        except Exception:
            pass

    def _sync_from_backend(self) -> None:
        if self._sync_job is not None:
            try:
                self.after_cancel(self._sync_job)
            except Exception:
                pass
            self._sync_job = None
        if self._is_destroyed or self._mongo_attendance is None or self._employee_id is None:
            return
        self._run_backend(
            lambda: self._mongo_attendance.refresh_state(self._employee_id),
            on_success=self._accept_state,
            action_name="Attendance sync",
        )
        if not self._is_destroyed:
            self._sync_job = self.after(self.REFRESH_SECONDS * 1000, self._sync_from_backend)

    def _accept_state(self, state: dict) -> None:
        self._state = state
        self._render_state()

    def _schedule_local_tick(self) -> None:
        if self._is_destroyed:
            return
        self._render_state()
        self._update_job = self.after(1000, self._schedule_local_tick)

    def _render_state(self) -> None:
        if self._is_destroyed:
            return
        state = self._state or {"state": "not_started", "status": "not_started", "record": None}
        current_state = state.get("state", "not_started")
        current_status = state.get("status", "clocked_out")
        record = state.get("record")

        if current_state == "working" or current_status == "clocked_in":
            label, color = "🟢 Clocked In", Theme.SUCCESS
            elapsed = self._mongo_attendance.get_live_seconds(record) if self._mongo_attendance else 0
            self.clock_button.configure(text="Clock Out", fg_color=Theme.DANGER, hover_color="#C62828", state="normal")
            self.break_button.configure(text="Start Break", fg_color=Theme.WARNING, hover_color="#F57C00", state="normal")
        elif current_state == "on_break" or current_status == "on_break":
            label, color = "☕ On Break", Theme.WARNING
            elapsed = self._mongo_attendance.get_live_seconds(record) if self._mongo_attendance else 0
            self.clock_button.configure(text="Clock Out", fg_color=Theme.DANGER, hover_color="#C62828", state="normal")
            self.break_button.configure(text="End Break", fg_color=Theme.SUCCESS, hover_color="#2E7D32", state="normal")
        elif current_state == "completed" or current_status == "clocked_out":
            label, color = "🔴 Clocked Out", Theme.DANGER
            elapsed = int(float(record.get("hours_worked") or 0) * 3600) if record else 0
            self.clock_button.configure(text="Clock In", fg_color=Theme.SUCCESS, hover_color="#2E7D32", state="disabled")
            self.break_button.configure(text="Break", fg_color=Theme.PANEL_ALT, state="disabled")
        else:
            label, color, elapsed = "🔴 Not Clocked In", Theme.DANGER, 0
            self.clock_button.configure(text="Clock In", fg_color=Theme.SUCCESS, hover_color="#2E7D32", state="normal")
            self.break_button.configure(text="Break", fg_color=Theme.PANEL_ALT, state="disabled")

        self.status_label.configure(text=label, text_color=color)
        self.timer_display.configure(text=self._format_seconds(elapsed))
        if self._busy:
            self.clock_button.configure(state="disabled")
            self.break_button.configure(state="disabled")

    @staticmethod
    def _format_seconds(total_seconds) -> str:
        try:
            total_seconds = max(0, int(float(total_seconds or 0)))
        except (TypeError, ValueError):
            total_seconds = 0
        return f"{total_seconds // 3600:02d}:{(total_seconds % 3600) // 60:02d}:{total_seconds % 60:02d}"

    def _toggle_clock(self) -> None:
        if self._busy or self._is_destroyed or not self._state or self._mongo_attendance is None:
            return
        current_state = self._state.get("state", "not_started")
        current_status = self._state.get("status", "clocked_out")
        if current_state == "not_started" or (current_status == "clocked_out" and not self._state.get("record")):
            op = lambda: self._mongo_attendance.clock_in(self._employee_id)
            name = "Clock in"
        elif current_state == "completed" or current_status == "clocked_out":
            print("⚠️ Today's attendance has already been completed.")
            return
        elif current_state == "on_break":
            print("⚠️ End the active break before clocking out.")
            return
        else:
            op = lambda: self._mongo_attendance.clock_out(self._employee_id)
            name = "Clock out"
        self._run_backend(op, on_success=self._accept_state, action_name=name)

    def _toggle_break(self) -> None:
        if self._busy or self._is_destroyed or not self._state or self._mongo_attendance is None:
            return
        current_state = self._state.get("state", "not_started")
        current_status = self._state.get("status", "clocked_out")
        if current_state == "working" or current_status == "clocked_in":
            op, name = lambda: self._mongo_attendance.start_break(self._employee_id), "Start break"
        elif current_state == "on_break" or current_status == "on_break":
            op, name = lambda: self._mongo_attendance.end_break(self._employee_id), "End break"
        else:
            print("⚠️ No active attendance session.")
            return
        self._run_backend(op, on_success=self._accept_state, action_name=name)

    def update_employee(self, employee_id, employee_name) -> None:
        self._employee_id = employee_id
        self._employee_name = employee_name
        self._state = None
        self._sync_from_backend()

    def pause(self) -> None:
        for job in (self._update_job, self._sync_job, self._queue_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._update_job = self._sync_job = self._queue_job = None

    def resume(self) -> None:
        if not self._is_destroyed:
            if self._queue_job is None:
                self._queue_job = self.after(50, self._drain_backend_queue)
            self._sync_from_backend()
            self._schedule_local_tick()

    def destroy(self) -> None:
        if self._is_destroyed:
            return
        self._is_destroyed = True
        for job in (self._update_job, self._sync_job, self._queue_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._update_job = self._sync_job = self._queue_job = None
        try:
            super().destroy()
        except Exception:
            pass

