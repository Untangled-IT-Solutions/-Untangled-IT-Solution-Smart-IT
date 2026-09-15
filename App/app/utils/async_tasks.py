"""Background-task helper for the CustomTkinter UI.

Worker threads must not call Tk APIs directly. Results are placed on a
thread-safe queue and drained by a main-thread poller started via
``start_ui_dispatcher(root)``.

This avoids the Python 3.13+/3.14 error:
    RuntimeError: main thread is not in main loop
when scheduling ``after`` from a background thread.
"""
from __future__ import annotations

import queue
import threading
import traceback
from typing import Any, Callable, Optional

# Cross-thread hand-off. Workers only put; the UI poller only get.
_UI_QUEUE: queue.Queue[Callable[[], None]] = queue.Queue()
_POLL_MS = 50


def _drain_ui_queue() -> None:
    """Run all pending UI callbacks on the Tk thread."""
    for _ in range(100):
        try:
            callback = _UI_QUEUE.get_nowait()
        except queue.Empty:
            break
        try:
            callback()
        except Exception:
            traceback.print_exc()


def start_ui_dispatcher(root: Any) -> None:
    """One poller per root; login and main windows have distinct lifetimes."""
    if getattr(root, '_nexus_dispatcher_started', False):
        return
    root._nexus_dispatcher_started = True
    def poll():
        try:
            if not root.winfo_exists():
                return
            _drain_ui_queue()
            root.after(_POLL_MS, poll)
        except Exception:
            root._nexus_dispatcher_started = False
    root.after(_POLL_MS, poll)


def _schedule_on_ui(owner: Any, callback: Callable[[], None]) -> None:
    """Workers only enqueue. All Tk calls execute in the main-thread poller."""
    def deliver():
        try:
            exists = owner.winfo_exists()
        except Exception:
            return
        if exists and not getattr(owner, '_is_destroyed', False) and not getattr(owner, '_destroyed', False):
            callback()
    _UI_QUEUE.put(deliver)


def run_in_background(
    owner: Any,
    operation: Callable[[], Any],
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    *,
    name: str = "nexus-worker",
) -> threading.Thread:
    """Run ``operation`` off the Tk thread and marshal its result back."""

    start_ui_dispatcher(owner.winfo_toplevel())

    def worker() -> None:
        try:
            result = operation()
        except Exception as exc:  # pragma: no cover - depends on runtime I/O
            traceback.print_exc()
            if on_error is not None:
                def report(error=exc) -> None:
                    try:
                        on_error(error)
                    except Exception:
                        traceback.print_exc()

                _schedule_on_ui(owner, report)
            return

        if on_success is not None:
            def deliver(value=result) -> None:
                try:
                    on_success(value)
                except Exception:
                    traceback.print_exc()

            _schedule_on_ui(owner, deliver)

    thread = threading.Thread(target=worker, name=name, daemon=True)
    thread.start()
    return thread