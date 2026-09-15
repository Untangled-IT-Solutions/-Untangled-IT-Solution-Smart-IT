# app/views/login_view.py
"""Untangled Nexus Login View — polished, responsive UI."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, NamedTuple

import customtkinter as ctk

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

from app.controllers.login_controller import LoginController
from app.utils.theme import Theme
from app.utils.ui_tasks import ui_task, RemoteCall


class _WorkArea(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)


class LoginView(ctk.CTk):
    """Modern Untangled Nexus login window."""

    PRIMARY = "#60920D"
    PRIMARY_HOVER = "#74AE10"
    PRIMARY_DARK = "#3F6508"
    PRIMARY_SOFT = "#E8F5E0"
    BRIGHT = "#6CE000"

    ERROR = "#D64545"
    DISABLED = "#8A958C"
    FONT = "Segoe UI"

    MIN_W, MIN_H = 420, 500
    PREFERRED_W = 920
    PREFERRED_H = 540
    LARGE_W = 960
    LARGE_H = 560

    DESKTOP_SPLIT = 860
    HEIGHT_LARGE = 600
    HEIGHT_NORMAL = 540
    HEIGHT_COMPACT = 500

    def __init__(self, controller: LoginController) -> None:
        super().__init__()

        self._controller = controller
        self._is_destroyed = False
        self._login_success = False
        self._password_visible = False
        self._resize_job = None
        self._layout_mode = "normal_desktop"
        self._last_metrics_key: tuple | None = None
        self._current_metrics: dict | None = None

        self._ctk_images: list = []
        self._logo_labels: list = []

        self.title(f"{Theme.COMPANY_NAME} | Login")
        self.minsize(self.MIN_W, self.MIN_H)
        self.configure(fg_color=self._bg())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # ------------------------------------------------------------------
        # Window / Taskbar icon  (assets/Branding/icon.ico)
        # ------------------------------------------------------------------
        self._set_window_icon()

        self._set_geometry()
        self.update_idletasks()
        self._build()

        self.bind("<Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Configure>", self._on_resize, add="+")

        self._logos_mounted = False
        self.bind("<Map>", self._on_first_map, add="+")
        self.after(200, self._focus_username)
        self.after_idle(self._apply_layout)
        self.after(60, self._set_geometry)
        self.deiconify()
        self.lift()
        self.focus_force()

    # ------------------------------------------------------------------ icon
    def _set_window_icon(self) -> None:
        """Set the window and taskbar icon from assets/Branding/icon.ico"""
        try:
            # Primary location requested by user
            candidates = [
                Path(__file__).resolve().parents[2] / "assets" / "Branding" / "icon.ico",
                Path(__file__).resolve().parents[1] / "assets" / "Branding" / "icon.ico",
                Path.cwd() / "assets" / "Branding" / "icon.ico",
                Path.cwd() / "assets" / "icon.ico",
            ]

            icon_path = None
            for p in candidates:
                if p.is_file():
                    icon_path = p
                    break

            if icon_path is None:
                print("⚠️ Window icon not found. Looked for: assets/Branding/icon.ico")
                return

            # .ico works best on Windows for both title-bar and taskbar
            self.iconbitmap(str(icon_path))
            print(f"✅ Window icon set: {icon_path}")

        except Exception as e:
            print(f"⚠️ Could not set window icon: {e}")

    # ------------------------------------------------------------------ theme
    def _is_dark(self) -> bool:
        try:
            return str(getattr(Theme, "CURRENT_MODE", "light")).lower() == "dark"
        except Exception:
            return ctk.get_appearance_mode().lower() == "dark"

    def _pick(self, light: str, dark: str) -> str:
        return dark if self._is_dark() else light

    def _bg(self) -> str:
        return self._pick("#F3F6F0", "#0B100D")

    def _panel(self) -> str:
        return self._pick("#FFFFFF", "#121A14")

    def _input_bg(self) -> str:
        return self._pick("#FFFFFF", "#1A241C")

    def _border(self) -> str:
        return self._pick("#D5DDD0", "#2A382E")

    def _text(self) -> str:
        return self._pick("#16201A", "#F2F6F1")

    def _muted(self) -> str:
        return self._pick("#6B776C", "#95A396")

    def _font(self, size: int, bold: bool = False):
        return (self.FONT, size, "bold") if bold else (self.FONT, size)

    # ------------------------------------------------------------------ work area
    def _get_work_area(self) -> _WorkArea:
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", wintypes.LONG),
                        ("top", wintypes.LONG),
                        ("right", wintypes.LONG),
                        ("bottom", wintypes.LONG),
                    ]

                SPI_GETWORKAREA = 0x0030
                rect = RECT()
                if ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
                ):
                    return _WorkArea(rect.left, rect.top, rect.right, rect.bottom)
            except Exception:
                pass

        try:
            sw = int(self.winfo_screenwidth())
            sh = int(self.winfo_screenheight())
        except Exception:
            sw, sh = 1280, 720
        return _WorkArea(0, 0, sw, max(sh - 56, self.MIN_H + 20))

    def _calculate_window_size(self) -> tuple[int, int, int, int]:
        wa = self._get_work_area()
        avail_w = max(self.MIN_W, wa.width - 16)
        avail_h = max(self.MIN_H, wa.height - 16)

        if avail_w >= self.LARGE_W + 30 and avail_h >= self.LARGE_H + 30:
            w, h = self.LARGE_W, self.LARGE_H
        elif avail_w >= self.PREFERRED_W and avail_h >= self.PREFERRED_H:
            w, h = self.PREFERRED_W, self.PREFERRED_H
        else:
            w = min(self.PREFERRED_W, avail_w)
            h = min(self.PREFERRED_H, avail_h)
            if w < self.DESKTOP_SPLIT and avail_w >= 480:
                w = min(520, avail_w)

        w = max(self.MIN_W, min(w, avail_w))
        h = max(self.MIN_H, min(h, avail_h))

        x = wa.left + max(0, (wa.width - w) // 2)
        y = wa.top + max(0, (wa.height - h) // 2)
        return w, h, x, y

    def _set_geometry(self) -> None:
        if self._is_destroyed:
            return
        try:
            w, h, x, y = self._calculate_window_size()
            self.geometry(f"{w}x{h}+{x}+{y}")
            # Lock max size so the window cannot grow beyond its designed dimensions
            self.maxsize(w, h)
            # On Windows also hide the maximize button from the title bar
            self._disable_maximize_button()
        except Exception:
            pass

    def _disable_maximize_button(self) -> None:
        """Remove the maximize (zoom) button from the title bar on Windows."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            # CTk/Tk windows are often nested — get the real top-level HWND
            hwnd = self.winfo_id()
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                hwnd = parent

            GWL_STYLE = -16
            WS_MAXIMIZEBOX = 0x00010000

            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            # Clear maximize box; leave size borders so the window stays resizable
            style = style & ~WS_MAXIMIZEBOX
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            # Force the non-client area to redraw so the button disappears
            SWP_FRAMECHANGED = 0x0020
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ metrics
    def _calculate_layout_metrics(self, w: int, h: int) -> dict:
        if w >= self.DESKTOP_SPLIT and h >= self.HEIGHT_LARGE:
            mode = "large_desktop"
        elif w >= self.DESKTOP_SPLIT and h >= self.HEIGHT_NORMAL:
            mode = "normal_desktop"
        elif w >= self.DESKTOP_SPLIT:
            mode = "compact_desktop"
        else:
            mode = "small"

        left_approx = int(w * 0.45)
        logo_w = max(220, int(left_approx * 0.82))
        logo_h = int(logo_w * 0.62)

        if mode == "large_desktop":
            return {
                "mode": mode,
                "form_padx": 40, "form_pady": 18,
                "brand_padx": 28, "brand_pady": 20,
                "input_h": 44, "btn_h": 46, "show_w": 60,
                "gap_label": 4, "gap_section": 10,
                "gap_welcome": 6, "gap_subtitle": 12,
                "gap_error": 6, "gap_login": 12,
                "gap_demo": 14, "gap_foot": 10,
                "demo_padx": 12, "demo_pady_top": 8, "demo_pady_bot": 8,
                "heading_size": 24,
                "logo_brand": (logo_w, logo_h),
                "logo_compact": (150, 52),
                "center_form": True,
            }
        if mode == "normal_desktop":
            return {
                "mode": mode,
                "form_padx": 32, "form_pady": 14,
                "brand_padx": 24, "brand_pady": 16,
                "input_h": 42, "btn_h": 44, "show_w": 58,
                "gap_label": 3, "gap_section": 9,
                "gap_welcome": 4, "gap_subtitle": 10,
                "gap_error": 5, "gap_login": 10,
                "gap_demo": 12, "gap_foot": 8,
                "demo_padx": 11, "demo_pady_top": 7, "demo_pady_bot": 7,
                "heading_size": 22,
                "logo_brand": (logo_w, logo_h),
                "logo_compact": (140, 48),
                "center_form": True,
            }
        if mode == "compact_desktop":
            return {
                "mode": mode,
                "form_padx": 26, "form_pady": 10,
                "brand_padx": 18, "brand_pady": 12,
                "input_h": 40, "btn_h": 42, "show_w": 56,
                "gap_label": 3, "gap_section": 7,
                "gap_welcome": 2, "gap_subtitle": 8,
                "gap_error": 4, "gap_login": 8,
                "gap_demo": 8, "gap_foot": 6,
                "demo_padx": 10, "demo_pady_top": 6, "demo_pady_bot": 6,
                "heading_size": 20,
                "logo_brand": (max(200, int(logo_w * 0.9)), max(120, int(logo_h * 0.9))),
                "logo_compact": (130, 44),
                "center_form": False,
            }
        return {
            "mode": mode,
            "form_padx": 20, "form_pady": 10,
            "brand_padx": 16, "brand_pady": 10,
            "input_h": 40, "btn_h": 42, "show_w": 56,
            "gap_label": 3, "gap_section": 7,
            "gap_welcome": 2, "gap_subtitle": 8,
            "gap_error": 4, "gap_login": 8,
            "gap_demo": 8, "gap_foot": 6,
            "demo_padx": 10, "demo_pady_top": 6, "demo_pady_bot": 6,
            "heading_size": 20,
            "logo_brand": (180, 110),
            "logo_compact": (140, 48),
            "center_form": False,
        }

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._shell = ctk.CTkFrame(self, fg_color="transparent")
        self._shell.grid(row=0, column=0, sticky="nsew")
        self._shell.grid_rowconfigure(0, weight=1)
        self._shell.grid_columnconfigure(0, weight=1)
        self._shell.grid_columnconfigure(1, weight=1)

        # Left brand panel
        self._brand_panel = ctk.CTkFrame(self._shell, fg_color=self.PRIMARY, corner_radius=0)
        self._brand_panel.grid(row=0, column=0, sticky="nsew")
        self._brand_panel.grid_rowconfigure(0, weight=1)
        self._brand_panel.grid_columnconfigure(0, weight=1)

        self._brand_inner = ctk.CTkFrame(self._brand_panel, fg_color="transparent")
        self._brand_inner.grid(row=0, column=0, sticky="nsew", padx=28, pady=20)
        self._brand_inner.grid_columnconfigure(0, weight=1)

        self._brand_inner.grid_rowconfigure(0, weight=2)
        self._brand_inner.grid_rowconfigure(1, weight=0)
        self._brand_inner.grid_rowconfigure(2, weight=1)
        self._brand_inner.grid_rowconfigure(3, weight=0)
        self._brand_inner.grid_rowconfigure(4, weight=0)
        self._brand_inner.grid_rowconfigure(5, weight=0)
        self._brand_inner.grid_rowconfigure(6, weight=0)

        self._brand_logo_host = ctk.CTkFrame(self._brand_inner, fg_color="transparent")
        self._brand_logo_host.grid(row=1, column=0, sticky="")
        self._brand_logo_placeholder = ctk.CTkLabel(
            self._brand_logo_host, text="UNTANGLED",
            font=self._font(28, True), text_color="#FFFFFF",
        )
        self._brand_logo_placeholder.grid(row=0, column=0)

        self._brand_title = ctk.CTkLabel(
            self._brand_inner, text="Untangled Nexus Workplace",
            font=self._font(22, True), text_color="#FFFFFF", anchor="w",
        )
        self._brand_title.grid(row=3, column=0, sticky="w", pady=(8, 2))

        self._brand_sub = ctk.CTkLabel(
            self._brand_inner, text=Theme.SUBTITLE,
            font=self._font(13), text_color="#E5F5D4", anchor="w",
        )
        self._brand_sub.grid(row=4, column=0, sticky="w")

        self._brand_desc = ctk.CTkLabel(
            self._brand_inner,
            text="Secure employee access to quotes,\nattendance, and operations.",
            font=self._font(12), text_color="#D7EBC4",
            justify="left", anchor="w",
        )
        self._brand_desc.grid(row=5, column=0, sticky="w", pady=(12, 0))

        self._brand_ver = ctk.CTkLabel(
            self._brand_inner, text=f"v{Theme.VERSION}",
            font=self._font(11), text_color="#C5DEA8", anchor="w",
        )
        self._brand_ver.grid(row=6, column=0, sticky="w", pady=(14, 0))

        # Right form panel
        self._form_panel = ctk.CTkFrame(self._shell, fg_color=self._panel(), corner_radius=0)
        self._form_panel.grid(row=0, column=1, sticky="nsew")
        self._form_panel.grid_rowconfigure(0, weight=1)
        self._form_panel.grid_columnconfigure(0, weight=1)

        self._form_center = ctk.CTkFrame(self._form_panel, fg_color="transparent")
        self._form_center.grid(row=0, column=0, sticky="nsew")
        self._form_center.grid_rowconfigure(0, weight=1)
        self._form_center.grid_rowconfigure(2, weight=1)
        self._form_center.grid_columnconfigure(0, weight=1)

        form = ctk.CTkFrame(self._form_center, fg_color="transparent")
        form.grid(row=1, column=0, sticky="ew", padx=36, pady=16)
        form.grid_columnconfigure(0, weight=1)
        self._form = form

        self._compact_brand = ctk.CTkFrame(form, fg_color="transparent")
        self._compact_brand.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self._compact_brand.grid_columnconfigure(0, weight=1)

        self._compact_logo_host = ctk.CTkFrame(self._compact_brand, fg_color="transparent")
        self._compact_logo_host.grid(row=0, column=0)
        self._compact_logo_placeholder = ctk.CTkLabel(
            self._compact_logo_host, text="UNTANGLED",
            font=self._font(18, True), text_color=self.PRIMARY,
        )
        self._compact_logo_placeholder.grid(row=0, column=0)

        self._compact_title = ctk.CTkLabel(
            self._compact_brand, text=Theme.COMPANY_NAME,
            font=self._font(16, True), text_color=self._text(),
        )
        self._compact_title.grid(row=1, column=0, pady=(6, 0))
        self._compact_sub = ctk.CTkLabel(
            self._compact_brand, text=Theme.SUBTITLE,
            font=self._font(11), text_color=self._muted(),
        )
        self._compact_sub.grid(row=2, column=0, pady=(1, 0))

        self._welcome_lbl = ctk.CTkLabel(
            form, text="Welcome back",
            font=self._font(22, True), text_color=self._text(), anchor="w",
        )
        self._welcome_lbl.grid(row=1, column=0, sticky="w", pady=(4, 2))

        self._subtitle_lbl = ctk.CTkLabel(
            form, text="Sign in with your Untangled account",
            font=self._font(12), text_color=self._muted(), anchor="w",
        )
        self._subtitle_lbl.grid(row=2, column=0, sticky="w", pady=(0, 12))

        self._user_lbl = ctk.CTkLabel(
            form, text="Email or username",
            font=self._font(12, True), text_color=self._muted(), anchor="w",
        )
        self._user_lbl.grid(row=3, column=0, sticky="w", pady=(0, 3))

        self.username_entry = ctk.CTkEntry(
            form, height=42,
            placeholder_text="name@untangled.co.za",
            border_color=self._border(), fg_color=self._input_bg(),
            text_color=self._text(), border_width=1, corner_radius=11,
            font=self._font(13), placeholder_text_color=self._muted(),
        )
        self.username_entry.grid(row=4, column=0, sticky="ew")
        self.username_entry.bind("<FocusIn>", lambda e: self._focus_entry(self.username_entry, True))
        self.username_entry.bind("<FocusOut>", lambda e: self._focus_entry(self.username_entry, False))

        self._pass_lbl = ctk.CTkLabel(
            form, text="Password",
            font=self._font(12, True), text_color=self._muted(), anchor="w",
        )
        self._pass_lbl.grid(row=5, column=0, sticky="w", pady=(10, 3))

        pass_row = ctk.CTkFrame(form, fg_color="transparent")
        pass_row.grid(row=6, column=0, sticky="ew")
        pass_row.grid_columnconfigure(0, weight=1)
        self._pass_row = pass_row

        self.password_entry = ctk.CTkEntry(
            pass_row, height=42,
            placeholder_text="Enter your password", show="●",
            border_color=self._border(), fg_color=self._input_bg(),
            text_color=self._text(), border_width=1, corner_radius=11,
            font=self._font(13), placeholder_text_color=self._muted(),
        )
        self.password_entry.grid(row=0, column=0, sticky="ew")
        self.password_entry.bind("<FocusIn>", lambda e: self._focus_entry(self.password_entry, True))
        self.password_entry.bind("<FocusOut>", lambda e: self._focus_entry(self.password_entry, False))

        self._show_pass_btn = ctk.CTkButton(
            pass_row, text="Show", width=58, height=42,
            fg_color=self._input_bg(),
            hover_color=self._pick("#EDF5E5", "#243128"),
            text_color=self._muted(), border_width=1,
            border_color=self._border(), corner_radius=11,
            font=self._font(12, True), command=self._toggle_password,
        )
        self._show_pass_btn.grid(row=0, column=1, padx=(8, 0))

        self.error_label = ctk.CTkLabel(
            form, text="", text_color=self.ERROR,
            font=self._font(12), anchor="w", justify="left", wraplength=320,
        )
        self.error_label.grid(row=7, column=0, sticky="ew", pady=(6, 0))

        self.login_button = ctk.CTkButton(
            form, text="Sign in", height=44,
            fg_color=self.PRIMARY, hover_color=self.PRIMARY_HOVER,
            text_color="#FFFFFF", corner_radius=11,
            font=self._font(14, True), command=self._submit,
        )
        self.login_button.grid(row=8, column=0, sticky="ew", pady=(10, 0))

        self._loading_label = ctk.CTkLabel(
            form, text="", font=self._font(12),
            text_color=self._muted(), anchor="w",
        )
        self._loading_label.grid(row=9, column=0, sticky="ew", pady=(3, 0))

        self._demo = ctk.CTkFrame(
            form, fg_color=self._pick(self.PRIMARY_SOFT, "#1A2818"),
            corner_radius=11, border_width=1,
            border_color=self._pick("#D0E6C0", "#2F4530"),
        )
        # Only show demo card when DEMO_USERNAME is configured in .env
        if os.getenv("DEMO_USERNAME", "").strip():
            self._demo.grid(row=10, column=0, sticky="ew", pady=(12, 0))
        else:
            self._demo.grid_remove()
        self._demo.grid_columnconfigure(0, weight=1)

        self._demo_title = ctk.CTkLabel(
            self._demo, text="Demo access",
            font=self._font(12, True),
            text_color=self._pick(self.PRIMARY_DARK, self.BRIGHT), anchor="w",
        )
        self._demo_title.grid(row=0, column=0, sticky="w", padx=11, pady=(7, 1))

        self._demo_fill_btn = ctk.CTkButton(
            self._demo, text="Fill", width=50, height=24,
            fg_color=self._pick("#D7EBC9", "#243228"),
            hover_color=self._pick("#C8E0B5", "#2C3D2C"),
            text_color=self._pick(self.PRIMARY_DARK, self.BRIGHT),
            corner_radius=7, font=self._font(11, True),
            command=self._auto_fill_demo,
        )
        self._demo_fill_btn.grid(row=0, column=1, padx=10, pady=(5, 1))

        self._demo_user_lbl = ctk.CTkLabel(
            self._demo,
            text=os.getenv("DEMO_USERNAME", "Local demo account") or "Local demo account",
            font=self._font(11), text_color=self._muted(), anchor="w",
        )
        self._demo_user_lbl.grid(row=1, column=0, columnspan=2, sticky="w", padx=11, pady=(0, 7))

        self._foot = ctk.CTkFrame(form, fg_color="transparent")
        self._foot.grid(row=11, column=0, sticky="ew", pady=(8, 0))
        self._foot.grid_columnconfigure(0, weight=1)
        self._foot.grid_columnconfigure(1, weight=1)

        self._secure_lbl = ctk.CTkLabel(
            self._foot, text="●  Secure connection",
            font=self._font(11), text_color=self.PRIMARY, anchor="w",
        )
        self._secure_lbl.grid(row=0, column=0, sticky="w")

        self._legal_lbl = ctk.CTkLabel(
            self._foot, text=Theme.COMPANY_LEGAL_NAME,
            font=self._font(10), text_color=self._muted(), anchor="e",
        )
        self._legal_lbl.grid(row=0, column=1, sticky="e")

    # ------------------------------------------------------------------ logo
    def _project_roots(self) -> list[Path]:
        here = Path(__file__).resolve()
        roots = [here.parents[2], here.parents[1], Path.cwd(), Path.cwd().parent]
        seen, out = set(), []
        for r in roots:
            try:
                key = str(r.resolve())
            except Exception:
                key = str(r)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    def _logo_candidates(self, prefer_white: bool) -> list[Path]:
        white_names = [
            "logo_white.png", "logo_slogan.png", "logo_full.png",
            "logo.png", "untangled_logo_white.png", "brand_logo.png"
        ]
        dark_names = [
            "logo_dark.png", "logo.png", "logo_full.png",
            "logo_black.png", "logo_white.png"
        ]
        names = white_names if prefer_white else dark_names
        dirs_rel = [
            Path("assets") / "Branding" / "logo", Path("assets") / "logo",
            Path("assets") / "images", Path("assets") / "Branding", Path("assets"),
        ]
        found: list[Path] = []
        try:
            if hasattr(Theme, "logo_for_current_mode"):
                p = Theme.logo_for_current_mode()
                if p and Path(p).exists():
                    found.append(Path(p))
        except Exception:
            pass
        for root in self._project_roots():
            for rel in dirs_rel:
                folder = root / rel
                if not folder.is_dir():
                    continue
                for name in names:
                    candidate = folder / name
                    if candidate.is_file():
                        found.append(candidate)
        uniq, seen = [], set()
        for p in found:
            key = str(p.resolve()) if p.exists() else str(p)
            if key not in seen:
                seen.add(key)
                uniq.append(p)
        return uniq

    def _mount_logos(self) -> None:
        if self._is_destroyed:
            return
        try:
            self.update_idletasks()
        except Exception:
            pass
        metrics = self._current_metrics or self._calculate_layout_metrics(
            self.winfo_width() or self.PREFERRED_W,
            self.winfo_height() or self.PREFERRED_H,
        )
        # Compact logo: white when on green field, otherwise dark/primary
        compact_on_green = (metrics.get("mode") == "small")
        ok_brand = self._put_logo(
            self._brand_logo_host, self._brand_logo_placeholder,
            prefer_white=True, size=metrics["logo_brand"], fallback_color="#FFFFFF",
        )
        ok_compact = self._put_logo(
            self._compact_logo_host, self._compact_logo_placeholder,
            prefer_white=compact_on_green, size=metrics["logo_compact"],
            fallback_color="#FFFFFF" if compact_on_green else self.PRIMARY,
        )
        if not ok_brand and not ok_compact:
            print(f"⚠️ Logo could not be rendered. Paths searched: {[str(r) for r in self._project_roots()]}")
        else:
            print(f"✅ Logo mounted (brand={ok_brand}, compact={ok_compact})")

    def _mount_compact_logo_white(self) -> None:
        """Force a white logo onto the compact host (used on green full-bleed mode)."""
        if self._is_destroyed:
            return
        metrics = self._current_metrics or self._calculate_layout_metrics(
            self.winfo_width() or self.PREFERRED_W,
            self.winfo_height() or self.PREFERRED_H,
        )
        # Clear any previous logo widgets so we don't stack them
        try:
            for child in self._compact_logo_host.winfo_children():
                if child is not self._compact_logo_placeholder:
                    try:
                        child.destroy()
                    except Exception:
                        pass
            self._compact_logo_placeholder.grid()
        except Exception:
            pass
        # Slightly larger logo when it's the only brand element
        size = metrics.get("logo_compact", (140, 48))
        size = (max(size[0], 160), max(size[1], 56))
        ok = self._put_logo(
            self._compact_logo_host, self._compact_logo_placeholder,
            prefer_white=True, size=size, fallback_color="#FFFFFF",
        )
        if ok:
            print("✅ Compact white logo mounted for green mode")
        else:
            # Fallback: keep the text placeholder visible and white
            try:
                self._compact_logo_placeholder.configure(
                    text="UNTANGLED", text_color="#FFFFFF",
                    font=self._font(18, True),
                )
                self._compact_logo_placeholder.grid()
            except Exception:
                pass

    def _on_first_map(self, event=None) -> None:
        if self._is_destroyed or self._logos_mounted:
            return
        if event is not None and event.widget is not self:
            return
        self._logos_mounted = True
        self.after(80, self._mount_logos)
        self.after(130, self._set_geometry)
        # Re-apply after the window is fully mapped so the title-bar style sticks
        self.after(180, self._disable_maximize_button)

    def _put_logo(self, host, placeholder, *, prefer_white: bool, size: tuple[int, int], fallback_color: str) -> bool:
        if Image is None:
            return False
        import tempfile
        import tkinter as tk
        candidates = self._logo_candidates(prefer_white)
        if not candidates:
            return False
        last_err = None
        for path in candidates:
            tmp_path = None
            try:
                pil = Image.open(path).convert("RGBA")

                target_w, target_h = size
                src_w, src_h = pil.size
                if src_w == 0 or src_h == 0:
                    continue
                scale = min(target_w / src_w, target_h / src_h)
                new_w = max(1, int(src_w * scale))
                new_h = max(1, int(src_h * scale))

                try:
                    resample = Image.Resampling.LANCZOS
                except AttributeError:
                    resample = Image.LANCZOS
                pil = pil.resize((new_w, new_h), resample)

                fd, tmp_path = tempfile.mkstemp(suffix=".png")
                import os as _os
                _os.close(fd)
                pil.save(tmp_path, format="PNG")
                photo = tk.PhotoImage(file=tmp_path, master=self)
                self._ctk_images.append(photo)
                if placeholder is not None:
                    try:
                        placeholder.grid_remove()
                    except Exception:
                        pass
                ctk_lbl = ctk.CTkLabel(host, text="")
                ctk_lbl.grid(row=0, column=0)
                inner = getattr(ctk_lbl, "_label", None)
                if inner is not None:
                    inner.configure(image=photo)
                    try:
                        inner.configure(text="")
                    except Exception:
                        pass
                    inner.image = photo
                else:
                    bg = self.PRIMARY if prefer_white else self._panel()
                    tkl = tk.Label(host, image=photo, text="", bg=bg, bd=0, highlightthickness=0)
                    tkl.grid(row=0, column=0)
                    tkl.image = photo
                    ctk_lbl = tkl
                ctk_lbl.image = photo
                self._logo_labels.append(ctk_lbl)
                return True
            except Exception as exc:
                last_err = exc
            finally:
                if tmp_path:
                    try:
                        import os as _os
                        _os.unlink(tmp_path)
                    except Exception:
                        pass
        return False

    # ------------------------------------------------------------------ compact green theme
    def _apply_compact_theme(self, *, green: bool) -> None:
        """When the window is narrow, flood the whole view with brand green
        so it feels like the left panel expanded to full width."""
        if self._is_destroyed:
            return
        try:
            if green:
                bg = self.PRIMARY
                panel = self.PRIMARY
                text = "#FFFFFF"
                muted = "#D7EBC4"
                soft = "#4A7A0A"
                input_bg = "#FFFFFF"
                input_text = "#16201A"
                border = "#C8E0B5"
                demo_bg = "#4A7A0A"
                demo_border = "#6BA01A"
                demo_title = self.BRIGHT
                secure = "#E5F5D4"
                legal = "#C5DEA8"
                show_hover = "#5A8A0C"
                login_fg = "#FFFFFF"
                login_hover = self.PRIMARY_HOVER
                login_bg = self.PRIMARY_DARK
            else:
                bg = self._bg()
                panel = self._panel()
                text = self._text()
                muted = self._muted()
                soft = self._pick(self.PRIMARY_SOFT, "#1A2818")
                input_bg = self._input_bg()
                input_text = self._text()
                border = self._border()
                demo_bg = soft
                demo_border = self._pick("#D0E6C0", "#2F4530")
                demo_title = self._pick(self.PRIMARY_DARK, self.BRIGHT)
                secure = self.PRIMARY
                legal = muted
                show_hover = self._pick("#EDF5E5", "#243128")
                login_fg = "#FFFFFF"
                login_hover = self.PRIMARY_HOVER
                login_bg = self.PRIMARY

            self.configure(fg_color=bg)
            self._form_panel.configure(fg_color=panel)
            self._form_center.configure(fg_color="transparent")
            self._form.configure(fg_color="transparent")

            # Compact brand header
            self._compact_title.configure(text_color=text)
            self._compact_sub.configure(text_color=muted)
            try:
                self._compact_logo_placeholder.configure(text_color="#FFFFFF" if green else self.PRIMARY)
            except Exception:
                pass

            # Form labels & text
            self._welcome_lbl.configure(text_color=text)
            self._subtitle_lbl.configure(text_color=muted)
            self._user_lbl.configure(text_color=muted)
            self._pass_lbl.configure(text_color=muted)
            self._loading_label.configure(text_color=muted)
            self.error_label.configure(text_color="#FFB4B4" if green else self.ERROR)

            # Inputs stay crisp white so they pop on the green field
            self.username_entry.configure(
                fg_color=input_bg, text_color=input_text,
                border_color=border, placeholder_text_color=muted if not green else "#8A958C",
            )
            self.password_entry.configure(
                fg_color=input_bg, text_color=input_text,
                border_color=border, placeholder_text_color=muted if not green else "#8A958C",
            )
            self._show_pass_btn.configure(
                fg_color=input_bg, text_color=muted if not green else "#4A5A4C",
                hover_color=show_hover, border_color=border,
            )

            # Primary action – slightly darker green so it still reads as a button
            self.login_button.configure(
                fg_color=login_bg, hover_color=login_hover, text_color=login_fg,
            )

            # Demo card
            self._demo.configure(fg_color=demo_bg, border_color=demo_border)
            self._demo_title.configure(text_color=demo_title)
            self._demo_user_lbl.configure(text_color=muted if not green else "#C5DEA8")
            self._demo_fill_btn.configure(
                fg_color=self._pick("#D7EBC9", "#243228") if not green else "#5A8A0C",
                hover_color=self._pick("#C8E0B5", "#2C3D2C") if not green else "#6BA01A",
                text_color=demo_title,
            )

            # Footer
            self._secure_lbl.configure(text_color=secure)
            self._legal_lbl.configure(text_color=legal)
        except Exception as exc:
            print(f"Compact theme error: {exc}")

    # ------------------------------------------------------------------ layout
    def _on_resize(self, event=None) -> None:
        if self._is_destroyed:
            return
        if event is not None and event.widget is not self:
            return
        # Soft safety net: if something still forces a maximized state, snap back
        try:
            if self.state() == "zoomed":
                self.state("normal")
                return
        except Exception:
            pass
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(50, self._apply_layout)

    def _apply_layout(self) -> None:
        self._resize_job = None
        if self._is_destroyed:
            return
        try:
            w = self.winfo_width()
            h = self.winfo_height()
            if w <= 1 or h <= 1:
                return

            metrics = self._calculate_layout_metrics(w, h)
            key = (
                metrics["mode"], metrics["form_padx"], metrics["form_pady"],
                metrics["input_h"], metrics["btn_h"], metrics["logo_brand"],
                metrics["mode"] == "small",  # force theme refresh when entering/leaving green mode
            )
            if key == self._last_metrics_key and self._current_metrics is not None:
                self.error_label.configure(
                    wraplength=max(180, min(380, (w // 2 if metrics["mode"] != "small" else w) - 60))
                )
                return

            self._last_metrics_key = key
            self._current_metrics = metrics
            self._layout_mode = metrics["mode"]
            split = metrics["mode"] != "small"

            if split:
                self._shell.grid_columnconfigure(0, weight=5)
                self._shell.grid_columnconfigure(1, weight=6)
                self._brand_panel.grid()
                self._compact_brand.grid_remove()
                self._brand_inner.grid_configure(
                    padx=metrics["brand_padx"], pady=metrics["brand_pady"]
                )
                # Restore normal (light/dark panel) look
                self._apply_compact_theme(green=False)
            else:
                self._shell.grid_columnconfigure(0, weight=0)
                self._shell.grid_columnconfigure(1, weight=1)
                self._brand_panel.grid_remove()
                self._compact_brand.grid()
                # Hide text labels — logo alone on the green field
                self._compact_title.grid_remove()
                self._compact_sub.grid_remove()
                # Full-window brand green when compact / small
                self._apply_compact_theme(green=True)
                # Ensure white logo is mounted on the green background
                self.after(30, self._mount_compact_logo_white)

            if metrics.get("center_form", False) and split:
                self._form_center.grid_rowconfigure(0, weight=1)
                self._form_center.grid_rowconfigure(2, weight=1)
                self._form.grid_configure(
                    padx=metrics["form_padx"], pady=metrics["form_pady"], sticky="ew"
                )
            else:
                self._form_center.grid_rowconfigure(0, weight=0)
                self._form_center.grid_rowconfigure(2, weight=0)
                self._form.grid_configure(
                    padx=metrics["form_padx"], pady=metrics["form_pady"], sticky="new"
                )

            self._welcome_lbl.configure(font=self._font(metrics["heading_size"], True))
            self._welcome_lbl.grid_configure(pady=(metrics["gap_welcome"], 2))
            self._subtitle_lbl.grid_configure(pady=(0, metrics["gap_subtitle"]))
            self._user_lbl.grid_configure(pady=(0, metrics["gap_label"]))
            self._pass_lbl.grid_configure(pady=(metrics["gap_section"], metrics["gap_label"]))

            try:
                self.username_entry.configure(height=metrics["input_h"])
                self.password_entry.configure(height=metrics["input_h"])
                self._show_pass_btn.configure(height=metrics["input_h"], width=metrics["show_w"])
                self.login_button.configure(height=metrics["btn_h"])
            except Exception:
                pass

            self.error_label.grid_configure(pady=(metrics["gap_error"], 0))
            self.login_button.grid_configure(pady=(metrics["gap_login"], 0))
            self._loading_label.grid_configure(pady=(3, 0))
            self._demo.grid_configure(pady=(metrics["gap_demo"], 0))
            self._demo_title.grid_configure(
                padx=metrics["demo_padx"], pady=(metrics["demo_pady_top"], 1)
            )
            self._demo_fill_btn.grid_configure(
                padx=metrics["demo_padx"], pady=(max(3, metrics["demo_pady_top"] - 2), 1)
            )
            self._demo_user_lbl.grid_configure(
                padx=metrics["demo_padx"], pady=(0, metrics["demo_pady_bot"])
            )
            self._foot.grid_configure(pady=(metrics["gap_foot"], 0))

            half = w // 2 if split else w
            avail = max(160, half - metrics["form_padx"] * 2 - 20)
            self.error_label.configure(wraplength=max(180, min(380, avail)))
            if avail < 280:
                self._legal_lbl.configure(font=self._font(9))
            else:
                self._legal_lbl.configure(font=self._font(10))

        except Exception as exc:
            print(f"Login layout error: {exc}")

    # ------------------------------------------------------------------ interactions
    def _focus_entry(self, entry, focused: bool) -> None:
        if self._is_destroyed:
            return
        try:
            entry.configure(
                border_color=self.PRIMARY if focused else self._border(),
                border_width=2 if focused else 1,
            )
        except Exception:
            pass

    def _toggle_password(self) -> None:
        if self._is_destroyed:
            return
        self._password_visible = not self._password_visible
        try:
            self.password_entry.configure(show="" if self._password_visible else "●")
            self._show_pass_btn.configure(
                text="Hide" if self._password_visible else "Show",
                text_color=self.PRIMARY if self._password_visible else self._muted(),
            )
        except Exception:
            pass

    def _focus_username(self) -> None:
        if self._is_destroyed:
            return
        try:
            if self.username_entry.winfo_exists():
                self.username_entry.focus_set()
        except Exception:
            pass

    def _auto_fill_demo(self) -> None:
        if self._is_destroyed:
            return
        demo_user = os.getenv("DEMO_USERNAME", "").strip()
        demo_pass = os.getenv("DEMO_PASSWORD", "")
        if not demo_user or not demo_pass:
            self.error_label.configure(
                text="Demo credentials are not configured. Set DEMO_USERNAME and DEMO_PASSWORD."
            )
            return
        self.username_entry.delete(0, "end")
        self.username_entry.insert(0, demo_user)
        self.password_entry.delete(0, "end")
        self.password_entry.insert(0, demo_pass)
        self.error_label.configure(text="")
        self.username_entry.configure(border_color=self.PRIMARY)
        self.password_entry.configure(border_color=self.PRIMARY)

    @ui_task
    def _submit(self) -> None:
        if self._is_destroyed or self._login_success:
            return
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            self.error_label.configure(text="Please enter your username and password.")
            return
        self.login_button.configure(
            state="disabled", text="Signing in…",
            fg_color=self.DISABLED, hover_color=self.DISABLED,
        )
        self._loading_label.configure(text="Connecting securely…")
        self.error_label.configure(text="")
        self.update_idletasks()
        try:
            success, message = yield RemoteCall(self._controller.login, username, password, notify_success=False)
            if self._is_destroyed:
                return
            if not success:
                self._reset_login_button()
                self._loading_label.configure(text="")
                self.error_label.configure(text=message or "Sign in failed.")
                self.username_entry.focus_set()
                return
            if self._controller.requires_password_change:
                self._loading_label.configure(text="Password change required", text_color=self.PRIMARY)
                PasswordChangeDialog(
                    self,
                    self._controller,
                    current_password=password,
                    on_complete=self._finish_login,
                    on_cancel=self._cancel_password_change,
                )
                self.password_entry.delete(0, "end")
                return
            self._finish_login()
        except Exception as exc:
            self._reset_login_button()
            self._loading_label.configure(text="")
            self.error_label.configure(text=f"Login error: {exc}")
            import traceback
            traceback.print_exc()

    def _finish_login(self) -> None:
        if self._is_destroyed or self._login_success:
            return
        self._login_success = True
        self._controller.complete_login()
        try:
            self.error_label.configure(text="")
            self._loading_label.configure(text="Signed in successfully", text_color=self.PRIMARY)
            self.login_button.configure(
                text="Welcome", fg_color=self.PRIMARY,
                hover_color=self.PRIMARY, state="normal",
            )
            self.after(200, self.withdraw)  # visual only; AppController quits mainloop
        except Exception:
            pass

    def _cancel_password_change(self) -> None:
        self.password_entry.delete(0, "end")
        self._loading_label.configure(text="")
        self.error_label.configure(text="Password change cancelled. Sign in again to continue.")
        self._reset_login_button()

    def _reset_login_button(self) -> None:
        try:
            self.login_button.configure(
                state="normal", text="Sign in",
                fg_color=self.PRIMARY, hover_color=self.PRIMARY_HOVER,
                text_color="#FFFFFF",
            )
        except Exception:
            pass

    def show(self) -> None:
        if self._is_destroyed:
            return
        self._login_success = False
        self._password_visible = False
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.username_entry.delete(0, "end")
            self.password_entry.delete(0, "end")
            self.password_entry.configure(show="●")
            self._show_pass_btn.configure(text="Show", text_color=self._muted())
            self.error_label.configure(text="")
            self._loading_label.configure(text="", text_color=self._muted())
            self._reset_login_button()
            self.after(100, self._focus_username)
            self.after(120, self._apply_layout)
            self.after(160, self._set_geometry)
            self.after(200, self._disable_maximize_button)
            if not self._logo_labels:
                self.after(10, self._mount_logos)
        except Exception:
            pass

    def destroy(self) -> None:
        if self._is_destroyed:
            return
        self._is_destroyed = True
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
            self._resize_job = None
        self._ctk_images.clear()
        self._logo_labels.clear()
        try:
            super().destroy()
        except Exception:
            pass


class PasswordChangeDialog(ctk.CTkToplevel):
    """Mandatory first-login password change using the temporary session."""

    def __init__(
        self,
        master: LoginView,
        controller: LoginController,
        *,
        current_password: str,
        on_complete: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._current_password = current_password
        self._on_complete = on_complete
        self._on_cancel = on_cancel
        self._closed = False

        self.title("Set a new password")
        self.geometry("430x360")
        self.resizable(False, False)
        self.configure(fg_color=master._bg())
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()

        panel = ctk.CTkFrame(self, fg_color=master._panel(), corner_radius=14)
        panel.pack(fill="both", expand=True, padx=22, pady=22)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel,
            text="Create your password",
            font=master._font(22, True),
            text_color=master._text(),
        ).grid(row=0, column=0, sticky="w", padx=22, pady=(22, 4))
        ctk.CTkLabel(
            panel,
            text="Your temporary password must be changed before Nexus opens.",
            font=master._font(12),
            text_color=master._muted(),
            wraplength=340,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=22, pady=(0, 16))

        self.new_password = ctk.CTkEntry(
            panel,
            placeholder_text="New password (at least 8 characters)",
            show="●",
            height=42,
        )
        self.new_password.grid(row=2, column=0, sticky="ew", padx=22, pady=6)
        self.confirm_password = ctk.CTkEntry(
            panel,
            placeholder_text="Confirm new password",
            show="●",
            height=42,
        )
        self.confirm_password.grid(row=3, column=0, sticky="ew", padx=22, pady=6)
        self.message = ctk.CTkLabel(
            panel,
            text="",
            text_color=master.ERROR,
            anchor="w",
            wraplength=340,
        )
        self.message.grid(row=4, column=0, sticky="ew", padx=22, pady=(5, 0))

        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.grid(row=5, column=0, sticky="ew", padx=22, pady=(14, 22))
        buttons.grid_columnconfigure((0, 1), weight=1)
        self.cancel_button = ctk.CTkButton(
            buttons, text="Cancel", fg_color=master.DISABLED, command=self._cancel
        )
        self.cancel_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.save_button = ctk.CTkButton(
            buttons,
            text="Save password",
            fg_color=master.PRIMARY,
            hover_color=master.PRIMARY_HOVER,
            command=self._save,
        )
        self.save_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.bind("<Return>", lambda _event: self._save())
        self.after(80, self.new_password.focus_set)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.save_button.configure(state=state, text="Saving..." if busy else "Save password")
        self.cancel_button.configure(state=state)

    @ui_task
    def _save(self) -> None:
        new_password = self.new_password.get()
        confirmation = self.confirm_password.get()
        if len(new_password) < 8:
            self.message.configure(text="Use at least 8 characters.")
            return
        if new_password != confirmation:
            self.message.configure(text="The new passwords do not match.")
            return
        if new_password == self._current_password:
            self.message.configure(text="Choose a password different from the temporary password.")
            return
        self._set_busy(True)
        self.message.configure(text="Changing password...", text_color="#60920D")
        success, message = yield RemoteCall(
            self._controller.change_password,
            self._current_password,
            new_password,
        )
        if not success:
            self._set_busy(False)
            self.message.configure(text=message or "Password change failed.", text_color="#D64545")
            return
        self._closed = True
        self._current_password = ""
        self.grab_release()
        self.destroy()
        self._on_complete()

    @ui_task
    def _cancel(self) -> None:
        if self._closed:
            return
        self._set_busy(True)
        yield RemoteCall(self._controller.cancel_pending_login)
        self._closed = True
        self._current_password = ""
        self.grab_release()
        self.destroy()
        self._on_cancel()
