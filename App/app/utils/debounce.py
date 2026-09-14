"""Debounce / throttle helpers for search boxes and refresh buttons (main-thread only)."""

from __future__ import annotations

from typing import Any, Callable, Optional


class Debouncer:
    """Collapse rapid UI events into a single callback after ``delay_ms``."""

    def __init__(self, widget: Any, delay_ms: int = 300) -> None:
        self._widget = widget
        self._delay = max(50, int(delay_ms))
        self._job: Optional[str] = None

    def call(self, callback: Callable[[], None]) -> None:
        self.cancel()
        try:
            self._job = self._widget.after(self._delay, callback)
        except Exception:
            self._job = None
            try:
                callback()
            except Exception:
                pass

    def cancel(self) -> None:
        job = self._job
        self._job = None
        if job is not None:
            try:
                self._widget.after_cancel(job)
            except Exception:
                pass


class Throttle:
    """Allow at most one fire per ``interval_ms`` (leading edge)."""

    def __init__(self, widget: Any, interval_ms: int = 1000) -> None:
        self._widget = widget
        self._interval = max(100, int(interval_ms))
        self._blocked = False
        self._job: Optional[str] = None

    def call(self, callback: Callable[[], None]) -> None:
        if self._blocked:
            return
        self._blocked = True
        try:
            callback()
        finally:
            try:
                self._job = self._widget.after(self._interval, self._unlock)
            except Exception:
                self._blocked = False

    def _unlock(self) -> None:
        self._blocked = False
        self._job = None
