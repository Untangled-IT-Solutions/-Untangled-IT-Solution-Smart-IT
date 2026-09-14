"""Main shell – identical structure to original: sidebar + header timer + workspace."""

from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core import theme
from app.core.assets import logo_pixmap, window_icon
from app.core.session import Session
from app.core.workers import run_async
from app.ui.widgets.loading_overlay import LoadingOverlay
from app.ui.widgets.nav_button import NavButton
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.people_page import PeoplePage
from app.ui.pages.notifications_page import NotificationsPage
from app.ui.pages.tasks_page import TasksPage
from app.ui.pages.attendance_page import AttendancePage
from app.ui.pages.placeholder_page import PlaceholderPage


NAV_ORDER = [
    "Dashboard", "People", "Attendance", "Calendar", "Approvals",
    "Office Requests", "Notifications", "Projects", "Tasks", "Reports",
    "Quote Management", "Order Management", "Settings",
]


class MainWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, session: Session, user: dict) -> None:
        super().__init__()
        self.session = session
        self.user = user
        self.setWindowTitle(theme.COMPANY_NAME)
        self.setWindowIcon(window_icon())
        self.resize(1360, 860)
        self._nav: Dict[str, NavButton] = {}
        self._pages: Dict[str, QWidget] = {}
        self._gen: Dict[str, int] = {}
        self._active = ""
        self._clock_seconds = 0
        self._build()
        self._start_header_clock()
        self.navigate("Dashboard")
        self._poll_badge()

    def _build(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Sidebar ----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(theme.SIDEBAR_WIDTH)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(14, 18, 14, 14)
        sl.setSpacing(6)

        pm = logo_pixmap(160, 120)
        if pm:
            logo = QLabel()
            logo.setPixmap(pm)
            logo.setAlignment(Qt.AlignCenter)
            sl.addWidget(logo)
        else:
            brand = QLabel("UNTANGLED")
            brand.setAlignment(Qt.AlignCenter)
            brand.setStyleSheet(
                f"color:{theme.PRIMARY}; font-weight:800; font-size:14px;"
            )
            sl.addWidget(brand)

        sub = QLabel(theme.SUBTITLE)
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color:{theme.MUTED}; font-size:10px; padding-bottom:8px;")
        sub.setWordWrap(True)
        sl.addWidget(sub)

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        host = QWidget()
        host.setStyleSheet("background:transparent;")
        nl = QVBoxLayout(host)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.setSpacing(4)
        for name in NAV_ORDER:
            btn = NavButton(name)
            btn.clicked.connect(self.navigate)
            nl.addWidget(btn)
            self._nav[name] = btn
        nl.addStretch(1)
        nav_scroll.setWidget(host)
        sl.addWidget(nav_scroll, 1)

        # ---- Right column ----
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        # Header
        top = QFrame()
        top.setObjectName("topBar")
        top.setFixedHeight(theme.HEADER_HEIGHT)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(28, 10, 24, 10)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        t1 = QLabel("Operations Workspace")
        t1.setStyleSheet("font-size:20px; font-weight:700;")
        t2 = QLabel(f"{theme.COMPANY_LEGAL} | {theme.SUBTITLE}")
        t2.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
        titles.addWidget(t1)
        titles.addWidget(t2)
        tl.addLayout(titles, 1)

        # Attendance cluster (matches original header)
        cluster = QFrame()
        cluster.setStyleSheet(
            f"background:{theme.PANEL_ALT}; border-radius:12px; border:1px solid {theme.BORDER};"
        )
        cl = QHBoxLayout(cluster)
        cl.setContentsMargins(10, 6, 10, 6)
        cl.setSpacing(8)
        self.clock_state = QLabel("● Clocked In")
        self.clock_state.setStyleSheet(f"color:{theme.SUCCESS}; font-weight:600; font-size:12px;")
        cl.addWidget(self.clock_state)
        self.timer_lbl = QLabel("00:00:00")
        self.timer_lbl.setStyleSheet("font-weight:700; font-size:14px; padding:0 6px;")
        cl.addWidget(self.timer_lbl)

        btns = QVBoxLayout()
        btns.setSpacing(4)
        self.btn_clock = QPushButton("Clock Out")
        self.btn_clock.setObjectName("danger")
        self.btn_clock.setFixedSize(100, 28)
        self.btn_break = QPushButton("Start Break")
        self.btn_break.setObjectName("warning")
        self.btn_break.setFixedSize(100, 28)
        btns.addWidget(self.btn_clock)
        btns.addWidget(self.btn_break)
        cl.addLayout(btns)
        tl.addWidget(cluster)

        logout = QPushButton("Logout")
        logout.setObjectName("secondary")
        logout.setFixedHeight(36)
        logout.clicked.connect(self.logout_requested.emit)
        tl.addWidget(logout)

        # Workspace
        content = QWidget()
        content.setStyleSheet(f"background:{theme.BG};")
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        c_lay.addWidget(self.stack)
        self.overlay = LoadingOverlay(content)

        right.addWidget(top)
        right.addWidget(content, 1)
        root.addWidget(sidebar)
        root.addLayout(right, 1)

        self.btn_clock.clicked.connect(lambda: self._attendance_action("clock-out"))
        self.btn_break.clicked.connect(lambda: self._attendance_action("break-start"))

    def _start_header_clock(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick)
        self._clock_timer.start(1000)

    def _tick(self) -> None:
        self._clock_seconds += 1
        h = self._clock_seconds // 3600
        m = (self._clock_seconds % 3600) // 60
        s = self._clock_seconds % 60
        self.timer_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _attendance_action(self, action: str) -> None:
        path = {
            "clock-in": "/api/attendance/clock-in",
            "clock-out": "/api/attendance/clock-out",
            "break-start": "/api/attendance/break/start",
            "break-end": "/api/attendance/break/end",
        }.get(action)
        if not path:
            return
        api = self.session.api

        def work():
            return api.request("POST", path, {})

        run_async(work, lambda _: None, lambda _: None)

    def navigate(self, name: str) -> None:
        for n, btn in self._nav.items():
            btn.set_active(n == name)
        self._active = name

        if name not in self._pages:
            page = self._make_page(name)
            self._pages[name] = page
            self.stack.addWidget(page)

        page = self._pages[name]
        self.stack.setCurrentWidget(page)
        self.overlay.show_message(f"Loading {name}…")

        gen = self._gen.get(name, 0) + 1
        self._gen[name] = gen

        if hasattr(page, "load"):
            page.load(
                generation=gen,
                is_current=lambda n=name, g=gen: self._gen.get(n) == g and self._active == n,
                on_done=lambda n=name: self._hide_loader(n),
            )
        else:
            QTimer.singleShot(150, self.overlay.hide)

    def _hide_loader(self, name: str) -> None:
        if self._active == name:
            self.overlay.hide()

    def _make_page(self, name: str) -> QWidget:
        if name == "Dashboard":
            return DashboardPage(self.session)
        if name == "People":
            return PeoplePage(self.session)
        if name == "Notifications":
            return NotificationsPage(self.session, on_unread=self._set_notif_badge)
        if name == "Tasks":
            return TasksPage(self.session)
        if name == "Attendance":
            return AttendancePage(self.session)
        return PlaceholderPage(name, self.session)

    def _set_notif_badge(self, count: int) -> None:
        btn = self._nav.get("Notifications")
        if btn:
            btn.set_badge(count)

    def _poll_badge(self) -> None:
        api = self.session.api

        def work():
            try:
                data = api.request("GET", "/api/notifications/unread-count")
                return int(data.get("count") or data.get("unread") or 0)
            except Exception:
                return 0

        def ok(count: int) -> None:
            self._set_notif_badge(count)
            QTimer.singleShot(45000, self._poll_badge)

        def err(_: str) -> None:
            QTimer.singleShot(60000, self._poll_badge)

        run_async(work, ok, err)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "overlay") and self.overlay.parent():
            self.overlay.setGeometry(self.overlay.parent().rect())
