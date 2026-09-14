"""Login – matches original CustomTkinter layout (green brand + white form)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core import theme
from app.core.assets import logo_pixmap, window_icon
from app.core.session import Session
from app.core.workers import run_async


class LoginWindow(QWidget):
    login_succeeded = Signal(dict)

    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        self.setWindowTitle(f"{theme.COMPANY_NAME} | Login")
        self.setWindowIcon(window_icon())
        self.setMinimumSize(920, 560)
        self.resize(980, 600)
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ===== LEFT: brand (exact green #60920D) =====
        brand = QFrame()
        brand.setObjectName("brandPanel")
        brand.setStyleSheet(
            f"QFrame#brandPanel {{ background-color: {theme.PRIMARY}; }}"
            "QLabel { background: transparent; }"
        )
        brand.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bl = QVBoxLayout(brand)
        bl.setContentsMargins(48, 56, 48, 40)
        bl.addStretch(2)

        pm = logo_pixmap(200, 160)
        if pm:
            logo = QLabel()
            logo.setPixmap(pm)
            logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            bl.addWidget(logo)
        else:
            badge = QLabel("U")
            badge.setFixedSize(80, 80)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                "background:#FFFFFF; color:#60920D; border-radius:18px;"
                "font-size:36px; font-weight:800;"
            )
            bl.addWidget(badge, 0, Qt.AlignLeft)

        name = QLabel(theme.COMPANY_LEGAL.upper())
        name.setStyleSheet("color:#FFFFFF; font-size:15px; font-weight:800; letter-spacing:1px;")
        bl.addWidget(name)
        bl.addSpacing(10)
        desc = QLabel(theme.SUBTITLE)
        desc.setStyleSheet("color:#D5E8B8; font-size:13px;")
        desc.setWordWrap(True)
        bl.addWidget(desc)
        bl.addStretch(3)
        foot = QLabel(f"v{theme.VERSION}")
        foot.setStyleSheet("color:#C5DEA8; font-size:11px;")
        bl.addWidget(foot)

        # ===== RIGHT: form =====
        form_wrap = QFrame()
        form_wrap.setStyleSheet(f"background:{theme.PANEL};")
        fl = QVBoxLayout(form_wrap)
        fl.setContentsMargins(56, 48, 56, 40)
        fl.addStretch(1)

        form = QVBoxLayout()
        form.setSpacing(4)
        form.setContentsMargins(0, 0, 0, 0)

        w = QLabel("Welcome back")
        w.setStyleSheet(f"font-size:26px; font-weight:700; color:{theme.TEXT};")
        form.addWidget(w)
        form.addWidget(self._muted("Sign in with your Untangled account"))
        form.addSpacing(20)

        form.addWidget(self._field_label("Email or username"))
        self.username = QLineEdit()
        self.username.setPlaceholderText("name@untangled.co.za")
        self.username.setMinimumHeight(46)
        form.addWidget(self.username)
        form.addSpacing(12)

        form.addWidget(self._field_label("Password"))
        pass_row = QHBoxLayout()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Enter your password")
        self.password.setMinimumHeight(46)
        self.password.returnPressed.connect(self._submit)
        pass_row.addWidget(self.password)
        self.show_btn = QPushButton("Show")
        self.show_btn.setObjectName("secondary")
        self.show_btn.setFixedSize(72, 46)
        self.show_btn.clicked.connect(self._toggle)
        pass_row.addWidget(self.show_btn)
        form.addLayout(pass_row)
        form.addSpacing(6)

        self.error = QLabel("")
        self.error.setStyleSheet(f"color:{theme.DANGER}; font-size:12px;")
        self.error.setWordWrap(True)
        form.addWidget(self.error)
        form.addSpacing(10)

        self.login_btn = QPushButton("Sign in")
        self.login_btn.setMinimumHeight(50)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._submit)
        form.addWidget(self.login_btn)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
        form.addWidget(self.status)

        fl.addLayout(form)
        fl.addStretch(2)

        bottom = QHBoxLayout()
        sec = QLabel("●  Secure connection")
        sec.setStyleSheet(f"color:{theme.MUTED}; font-size:11px;")
        bottom.addWidget(sec)
        bottom.addStretch(1)
        bottom.addWidget(self._muted(theme.COMPANY_LEGAL))
        fl.addLayout(bottom)

        root.addWidget(brand, 1)
        root.addWidget(form_wrap, 1)

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{theme.MUTED}; font-weight:600; font-size:12px;")
        return lbl

    def _muted(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
        return lbl

    def _toggle(self) -> None:
        if self.password.echoMode() == QLineEdit.Password:
            self.password.setEchoMode(QLineEdit.Normal)
            self.show_btn.setText("Hide")
        else:
            self.password.setEchoMode(QLineEdit.Password)
            self.show_btn.setText("Show")

    def reset(self) -> None:
        self.password.clear()
        self.error.clear()
        self.status.clear()
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Sign in")

    def _submit(self) -> None:
        user = self.username.text().strip()
        password = self.password.text()
        if not user or not password:
            self.error.setText("Enter username and password.")
            return
        self.error.clear()
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in…")
        self.status.setText("Connecting to server…")

        def work():
            return self.session.login(user, password)

        def ok(data: dict) -> None:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Sign in")
            self.status.clear()
            self.login_succeeded.emit(data)

        def err(msg: str) -> None:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Sign in")
            self.status.clear()
            self.error.setText(msg or "Login failed")

        run_async(work, ok, err)
