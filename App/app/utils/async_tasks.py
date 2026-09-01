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
_DISPATCHER_STARTED = False
_DISPATCHER_LOCK = threading.Lock()
_POLL_MS = 50


def _drain_ui_queue() -> None:
    """Run all pending UI callbacks on the Tk thread."""
    while True:
        try:
            callback = _UI_QUEUE.get_nowait()
        except queue.Empty:
            break
        try:
            callback()
        except Exception:
            traceback.print_exc()


def start_ui_dispatcher(root: Any) -> None:
    """Start a repeating main-thread poller on ``root`` (call once)."""
    global _DISPATCHER_STARTED
    with _DISPATCHER_LOCK:
        if _DISPATCHER_STARTED:
            return
        _DISPATCHER_STARTED = True

    def poll() -> None:
        _drain_ui_queue()
        try:
            if root.winfo_exists():
                root.after(_POLL_MS, poll)
        except Exception:
            # Root gone — stop polling.
            global _DISPATCHER_STARTED
            with _DISPATCHER_LOCK:
                _DISPATCHER_STARTED = False

    try:
        root.after(_POLL_MS, poll)
        print("✅ UI dispatcher started (queue poller)")
    except Exception as exc:
        with _DISPATCHER_LOCK:
            _DISPATCHER_STARTED = False
        print(f"❌ Could not start UI dispatcher: {exc}")


def _schedule_on_ui(owner: Any, callback: Callable[[], None]) -> None:
    """Queue ``callback`` for the main-thread poller.

    Also tries ``after(0, ...)`` for environments where cross-thread after
    still works; the queue is the reliable path on Python 3.13+.
    """
    _UI_QUEUE.put(callback)

    # Best-effort immediate wake-up (may fail on worker threads — that is OK).
    targets = []
    try:
        top = owner.winfo_toplevel()
        if top is not None:
            targets.append(top)
    except Exception:
        pass
    targets.append(owner)

    for target in targets:
        try:
            target.after(0, _drain_ui_queue)
            return
        except Exception:
            continue
    # Poller will pick it up within _POLL_MS if after() is blocked.


def run_in_background(
    owner: Any,
    operation: Callable[[], Any],
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    *,
    name: str = "nexus-worker",
) -> threading.Thread:
    """Run ``operation`` off the Tk thread and marshal its result back."""

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