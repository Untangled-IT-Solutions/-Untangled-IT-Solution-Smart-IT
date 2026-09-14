"""Background-task helper for the CustomTkinter UI.

Worker threads must not call Tk APIs directly. Results are placed on a
thread-safe queue and drained by a main-thread poller started via
``start_ui_dispatcher(root)``.

Also provides:
  - ThreadPoolExecutor for concurrent API work
  - generation tokens so stale responses never update the wrong page
"""
from __future__ import annotations

import queue
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

# Cross-thread hand-off. Workers only put; the UI poller only get.
_UI_QUEUE: queue.Queue[Callable[[], None]] = queue.Queue()
_DISPATCHER_STARTED = False
_DISPATCHER_LOCK = threading.Lock()
_POLL_MS = 40

# Shared pool – reuses threads instead of spawning one per click
_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="nexus-bg")

# Per-owner generation counters (stale response protection)
_GENERATIONS: dict[int, int] = {}
_GEN_LOCK = threading.Lock()


def bump_generation(owner: Any) -> int:
    """Invalidate in-flight loads for ``owner``. Returns the new generation id."""
    key = id(owner)
    with _GEN_LOCK:
        gen = _GENERATIONS.get(key, 0) + 1
        _GENERATIONS[key] = gen
        return gen


def current_generation(owner: Any) -> int:
    with _GEN_LOCK:
        return _GENERATIONS.get(id(owner), 0)


def is_generation_current(owner: Any, generation: int) -> bool:
    return current_generation(owner) == generation


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


def hide_global_nav_loading(owner: Any) -> None:
    """Hide MainWindow nav loader if present (safe from any widget)."""
    try:
        top = owner.winfo_toplevel() if owner is not None else None
        if top is not None and hasattr(top, "hide_nav_loading"):
            top.hide_nav_loading()
    except Exception:
        pass


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
    """Queue ``callback`` for the main-thread poller."""
    _UI_QUEUE.put(callback)
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


def run_in_background(
    owner: Any,
    operation: Callable[[], Any],
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
    *,
    name: str = "nexus-worker",
    generation: Optional[int] = None,
) -> None:
    """Run ``operation`` off the Tk thread; marshal result back to the UI thread.

    If ``generation`` is set, success/error callbacks are skipped when the
    owner's generation has moved on (user navigated away / refreshed again).
    """

    def worker() -> None:
        try:
            result = operation()
        except Exception as exc:
            traceback.print_exc()

            def report(error=exc) -> None:
                if generation is not None and not is_generation_current(owner, generation):
                    return
                try:
                    if on_error is not None:
                        on_error(error)
                except Exception:
                    traceback.print_exc()
                finally:
                    hide_global_nav_loading(owner)

            _schedule_on_ui(owner, report)
            return

        def deliver(value=result) -> None:
            if generation is not None and not is_generation_current(owner, generation):
                return
            try:
                if on_success is not None:
                    on_success(value)
            except Exception:
                traceback.print_exc()
            finally:
                hide_global_nav_loading(owner)

        _schedule_on_ui(owner, deliver)

    try:
        _EXECUTOR.submit(worker)
    except Exception:
        # Fallback if executor is shut down
        threading.Thread(target=worker, name=name, daemon=True).start()
