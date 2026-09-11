"""Professional CustomTkinter dialog for Untangled Nexus updates."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk

from app.services.update_service import UpdateInfo, UpdateService
from app.utils.theme import Theme

logger = logging.getLogger("untangled.update.ui")


class UpdateDialog(ctk.CTkToplevel):
    """Modal dialog: Update available / progress / result."""

    def __init__(
        self,
        master,
        update: UpdateInfo,
        current_version: str,
        update_service: UpdateService,
        on_install_started: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(master=master)
        self._update = update
        self._current_version = current_version.lstrip("v")
        self._service = update_service
        self._on_install_started = on_install_started
        self._busy = False
        self._installer_path: Optional[Path] = None

        self.title("Update Available")
        self.geometry("440x360")
        self.minsize(400, 320)
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_later)

        self._build()
        self._center_on_master(master)
        self.after(50, self.lift)
        self.after(80, self.focus_force)

    def _center_on_master(self, master) -> None:
        try:
            self.update_idletasks()
            mw = master.winfo_width()
            mh = master.winfo_height()
            mx = master.winfo_rootx()
            my = master.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            x = mx + max(0, (mw - w) // 2)
            y = my + max(0, (mh - h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _build(self) -> None:
        pad = Theme.SPACING

        ctk.CTkLabel(
            self,
            text="Update available",
            font=Theme.FONT_HEADING,
            text_color=Theme.TEXT,
        ).pack(padx=pad, pady=(pad, 4), anchor="w")

        ctk.CTkLabel(
            self,
            text="A new version of Untangled Nexus is ready.",
            font=Theme.FONT_BODY,
            text_color=Theme.MUTED_TEXT,
        ).pack(padx=pad, pady=(0, pad), anchor="w")

        card = ctk.CTkFrame(
            self,
            fg_color=Theme.PANEL,
            corner_radius=Theme.RADIUS,
            border_width=1,
            border_color=Theme.BORDER,
        )
        card.pack(fill="x", padx=pad, pady=(0, pad))

        versions = ctk.CTkFrame(card, fg_color="transparent")
        versions.pack(fill="x", padx=pad, pady=pad)
        versions.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            versions, text="Current version", font=Theme.FONT_SMALL, text_color=Theme.MUTED_TEXT
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            versions, text=f"v{self._current_version}", font=Theme.FONT_BODY, text_color=Theme.TEXT
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        ctk.CTkLabel(
            versions, text="→", font=Theme.FONT_HEADING, text_color=Theme.ACCENT
        ).grid(row=0, column=1, rowspan=2)

        ctk.CTkLabel(
            versions, text="New version", font=Theme.FONT_SMALL, text_color=Theme.MUTED_TEXT
        ).grid(row=0, column=2, sticky="e")
        ctk.CTkLabel(
            versions, text=f"v{self._update.version}", font=Theme.FONT_BODY, text_color=Theme.ACCENT
        ).grid(row=1, column=2, sticky="e", pady=(2, 0))

        ctk.CTkLabel(
            self,
            text="Nexus will close, install the update,\nand start again automatically.",
            font=Theme.FONT_SMALL,
            text_color=Theme.MUTED_TEXT,
            justify="left",
        ).pack(padx=pad, pady=(0, 8), anchor="w")

        self._status = ctk.CTkLabel(
            self, text="", font=Theme.FONT_SMALL, text_color=Theme.MUTED_TEXT,
            wraplength=380, justify="left",
        )
        self._status.pack(padx=pad, pady=(0, 4), anchor="w")

        self._progress = ctk.CTkProgressBar(
            self, height=8, progress_color=Theme.ACCENT, fg_color=Theme.PANEL_ALT,
        )
        self._progress.pack(fill="x", padx=pad, pady=(0, pad))
        self._progress.set(0)
        self._progress.pack_forget()

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=pad, pady=(0, pad))
        buttons.grid_columnconfigure((0, 1), weight=1)

        self._later_btn = ctk.CTkButton(
            buttons, text="Later", font=Theme.FONT_BUTTON,
            fg_color=Theme.PANEL_ALT, hover_color=Theme.BORDER, text_color=Theme.TEXT,
            height=40, command=self._on_later,
        )
        self._later_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self._update_btn = ctk.CTkButton(
            buttons, text="Update Now", font=Theme.FONT_BUTTON,
            fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER, text_color="#FFFFFF",
            height=40, command=self._on_update_now,
        )
        self._update_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        try:
            self._update_btn.configure(state=state)
            self._later_btn.configure(state=state)
        except Exception:
            pass

    def _on_later(self) -> None:
        if self._busy:
            return
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _on_update_now(self) -> None:
        if self._busy or self._service.is_downloading:
            return
        self._set_busy(True)
        self._status.configure(text="Downloading update…", text_color=Theme.MUTED_TEXT)
        self._progress.pack(fill="x", padx=Theme.SPACING, pady=(0, Theme.SPACING))
        self._progress.set(0)

        def worker() -> None:
            try:
                path = self._service.download_installer(
                    self._update, progress_callback=self._on_progress,
                )
                self.after(0, lambda: self._download_success(path))
            except Exception as exc:
                logger.exception("Update download failed")
                message = str(exc) or "Download failed."
                self.after(0, lambda: self._download_failed(message))

        threading.Thread(target=worker, name="nexus-update-download", daemon=True).start()

    def _on_progress(self, received: int, total: int) -> None:
        def apply() -> None:
            try:
                if total > 0:
                    self._progress.set(min(1.0, received / total))
                    mb_r = received / (1024 * 1024)
                    mb_t = total / (1024 * 1024)
                    self._status.configure(
                        text=f"Downloading… {mb_r:.1f} / {mb_t:.1f} MB",
                        text_color=Theme.MUTED_TEXT,
                    )
                else:
                    mb_r = received / (1024 * 1024)
                    self._status.configure(
                        text=f"Downloading… {mb_r:.1f} MB",
                        text_color=Theme.MUTED_TEXT,
                    )
            except Exception:
                pass

        try:
            self.after(0, apply)
        except Exception:
            pass

    def _download_success(self, path: Path) -> None:
        self._installer_path = path
        self._status.configure(text="Verified. Preparing to install…", text_color=Theme.SUCCESS)
        self._progress.set(1.0)
        try:
            self._service.install_update(path)
            if self._on_install_started:
                self._on_install_started()
            try:
                self.grab_release()
            except Exception:
                pass
            self.destroy()
        except Exception as exc:
            logger.exception("Failed to launch updater")
            self._download_failed(str(exc) or "Could not start the updater.")

    def _download_failed(self, message: str) -> None:
        self._set_busy(False)
        try:
            self._progress.pack_forget()
        except Exception:
            pass
        self._status.configure(text=message, text_color=Theme.DANGER)
        self._update_btn.configure(text="Retry")


class UpToDateDialog(ctk.CTkToplevel):
    """Simple modal when the user is already on the latest version."""

    def __init__(self, master, current_version: str) -> None:
        super().__init__(master=master)
        self.title("Check for Updates")
        self.geometry("360x180")
        self.resizable(False, False)
        self.configure(fg_color=Theme.BG)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        pad = Theme.SPACING
        ctk.CTkLabel(
            self,
            text="You are already running the latest version.",
            font=Theme.FONT_BODY,
            text_color=Theme.TEXT,
            wraplength=320,
        ).pack(padx=pad, pady=(pad, 8))
        ctk.CTkLabel(
            self,
            text=f"Version: v{current_version.lstrip('v')}",
            font=Theme.FONT_SMALL,
            text_color=Theme.MUTED_TEXT,
        ).pack(padx=pad, pady=(0, pad))
        ctk.CTkButton(
            self, text="OK", font=Theme.FONT_BUTTON,
            fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER, text_color="#FFFFFF",
            width=100, height=36, command=self._close,
        ).pack(pady=(0, pad))

        try:
            self.update_idletasks()
            mw = master.winfo_width()
            mh = master.winfo_height()
            mx = master.winfo_rootx()
            my = master.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            self.geometry(f"+{mx + max(0, (mw - w) // 2)}+{my + max(0, (mh - h) // 2)}")
        except Exception:
            pass
        self.after(50, self.lift)

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
