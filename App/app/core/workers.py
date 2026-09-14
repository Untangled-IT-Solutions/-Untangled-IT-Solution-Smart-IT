from __future__ import annotations
from typing import Any, Callable, Optional
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class Worker(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.fn())
        except Exception as exc:
            self.signals.error.emit(str(exc) or "Request failed")


def run_async(
    fn: Callable[[], Any],
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    *,
    generation: int = 0,
    expected_generation: Optional[Callable[[], int]] = None,
) -> None:
    worker = Worker(fn)

    def _ok(result: Any) -> None:
        if expected_generation is not None and expected_generation() != generation:
            return
        if on_success:
            on_success(result)

    def _err(msg: str) -> None:
        if expected_generation is not None and expected_generation() != generation:
            return
        if on_error:
            on_error(msg)

    worker.signals.finished.connect(_ok)
    worker.signals.error.connect(_err)
    QThreadPool.globalInstance().start(worker)
