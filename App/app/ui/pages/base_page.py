from __future__ import annotations
from typing import Any, Callable, Optional
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from app.core import cache, theme
from app.core.workers import run_async


class BasePage(QFrame):
    CACHE_KEY: Optional[str] = None
    CACHE_TTL = 40.0
    TITLE = "Page"
    SUBTITLE = ""

    def __init__(self, session) -> None:
        super().__init__()
        self.session = session
        self.setStyleSheet(f"background:{theme.BG};")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(28, 22, 28, 22)
        self._lay.setSpacing(10)
        t = QLabel(self.TITLE)
        t.setStyleSheet(f"font-size:22px; font-weight:700; color:{theme.TEXT};")
        self._lay.addWidget(t)
        if self.SUBTITLE:
            s = QLabel(self.SUBTITLE)
            s.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
            self._lay.addWidget(s)
        self.build()

    def build(self) -> None:
        pass

    def fetch(self) -> Any:
        return None

    def apply(self, data: Any) -> None:
        pass

    def load(
        self,
        *,
        generation: int = 0,
        is_current: Optional[Callable[[], bool]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        key = self.CACHE_KEY

        def finish_ok(data):
            if is_current is not None and not is_current():
                return
            try:
                self.apply(data)
            finally:
                if on_done:
                    on_done()

        def finish_err(_msg: str):
            if is_current is not None and not is_current():
                return
            if on_done:
                on_done()

        if key:
            cached = cache.get(key)
            if cached is not None:
                finish_ok(cached)

                def revalidate():
                    data = self.fetch()
                    cache.set(key, data, self.CACHE_TTL)
                    return data

                run_async(
                    revalidate,
                    on_success=lambda d: finish_ok(d) if (is_current is None or is_current()) else None,
                    on_error=lambda _m: None,
                    generation=generation,
                    expected_generation=lambda: generation,
                )
                return

        def work():
            data = self.fetch()
            if key:
                cache.set(key, data, self.CACHE_TTL)
            return data

        run_async(work, finish_ok, finish_err, generation=generation)
