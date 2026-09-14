from __future__ import annotations
from typing import Any
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from app.core import cache, theme
from app.core.workers import run_async
from app.ui.pages.base_page import BasePage


class AttendancePage(BasePage):
    TITLE = "Attendance"
    SUBTITLE = "Clock in / out and breaks"
    CACHE_KEY = "attendance"
    CACHE_TTL = 12.0

    def build(self) -> None:
        card = QFrame()
        card.setStyleSheet(
            f"background:{theme.PANEL}; border:1px solid {theme.BORDER}; border-radius:14px;"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        self.status = QLabel("Status: —")
        self.status.setStyleSheet("font-size:18px; font-weight:700;")
        cl.addWidget(self.status)
        self.detail = QLabel("")
        self.detail.setStyleSheet(f"color:{theme.MUTED};")
        cl.addWidget(self.detail)
        row = QHBoxLayout()
        self.btn_in = QPushButton("Clock In")
        self.btn_in.setObjectName("success")
        self.btn_in.setStyleSheet(
            f"background:{theme.SUCCESS}; color:white; border-radius:10px; padding:12px 20px;"
        )
        self.btn_out = QPushButton("Clock Out")
        self.btn_out.setObjectName("danger")
        self.btn_break = QPushButton("Start Break")
        self.btn_break.setObjectName("warning")
        self.btn_end = QPushButton("End Break")
        self.btn_end.setStyleSheet(
            f"background:{theme.INFO}; color:white; border-radius:10px; padding:12px 20px;"
        )
        for b, a in (
            (self.btn_in, "clock-in"),
            (self.btn_out, "clock-out"),
            (self.btn_break, "break-start"),
            (self.btn_end, "break-end"),
        ):
            b.setMinimumHeight(44)
            b.clicked.connect(lambda _=False, act=a: self._action(act))
            row.addWidget(b)
        cl.addLayout(row)
        self._lay.addWidget(card)
        self._lay.addStretch(1)

    def fetch(self) -> Any:
        try:
            return self.session.api.request("GET", "/api/attendance/status")
        except Exception as exc:
            return {"error": str(exc)}

    def apply(self, data: Any) -> None:
        data = data or {}
        if data.get("error"):
            self.status.setText("Status unavailable")
            self.detail.setText(str(data["error"]))
            return
        state = data.get("status") or data.get("state") or data
        if isinstance(state, dict):
            clocked = state.get("clocked_in") or state.get("is_clocked_in")
            on_break = state.get("on_break") or state.get("is_on_break")
            self.status.setText("Clocked In" if clocked else "Clocked Out")
            self.detail.setText(("On break · " if on_break else "") + str(state.get("message") or ""))
        else:
            self.status.setText(str(state))

    def _action(self, action: str) -> None:
        path = {
            "clock-in": "/api/attendance/clock-in",
            "clock-out": "/api/attendance/clock-out",
            "break-start": "/api/attendance/break/start",
            "break-end": "/api/attendance/break/end",
        }[action]

        def work():
            return self.session.api.request("POST", path, {})

        def ok(_):
            cache.invalidate("attendance")
            self.load(on_done=lambda: None)

        run_async(work, ok, lambda _m: None)
