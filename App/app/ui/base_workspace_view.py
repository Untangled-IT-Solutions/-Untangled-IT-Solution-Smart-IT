"""Base workspace view – instant shell, background data, cache, stale-safe.

Rules for subclasses:
  - Build widgets in ``build()`` only (no network I/O).
  - Load data in ``load_data()`` (worker thread only).
  - Apply results in ``apply_data()`` (main thread only).
  - Optional ``cache_key()`` for TTL reuse when navigating back.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import customtkinter as ctk

from app.utils import data_cache
from app.utils.async_tasks import (
    bump_generation,
    current_generation,
    hide_global_nav_loading,
    run_in_background,
)
from app.utils.theme import Theme

logger = logging.getLogger("untangled.ui")


class BaseWorkspaceView(ctk.CTkFrame):
    """Thin, consistent shell for Operations Workspace pages."""

    PAGE_TITLE = "Workspace"
    PAGE_SUBTITLE = ""
    # Soft cache TTL override (seconds); None → data_cache default by key prefix
    CACHE_TTL: Optional[float] = None

    def __init__(self, master: Any, **kwargs) -> None:
        fg = kwargs.pop("fg_color", Theme.BG)
        super().__init__(master, fg_color=fg, corner_radius=0, **kwargs)
        self._is_destroyed = False
        self._after_jobs: list[Any] = []
        self._loading_overlay: Optional[ctk.CTkFrame] = None
        self._error_banner: Optional[ctk.CTkFrame] = None
        self._has_applied_data = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._header = ctk.CTkFrame(self, fg_color="transparent")
        self._header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        self._title_label = ctk.CTkLabel(
            self._header,
            text=self.PAGE_TITLE,
            font=("Segoe UI", 22, "bold"),
            text_color=Theme.TEXT,
            anchor="w",
        )
        self._title_label.pack(anchor="w")
        if self.PAGE_SUBTITLE:
            ctk.CTkLabel(
                self._header,
                text=self.PAGE_SUBTITLE,
                font=("Segoe UI", 12),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).pack(anchor="w")

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self._body.grid_columnconfigure(0, weight=1)
        self._body.grid_rowconfigure(0, weight=1)

        self.build()

    # ------------------------------------------------------------------ hooks
    def build(self) -> None:
        """Create widgets. No network I/O."""

    def cache_key(self) -> Optional[str]:
        """Return a cache key for this page's data, or None to skip caching."""
        return None

    def load_data(self) -> Any:
        """Fetch data off the UI thread."""
        return None

    def apply_data(self, data: Any) -> None:
        """Apply data on the UI thread."""

    def on_load_error(self, error: Exception) -> None:
        logger.warning("%s load failed: %s", self.PAGE_TITLE, error)
        self.show_error(str(error) or "Could not load data")

    # ------------------------------------------------------------------ public
    def refresh(self, *, force: bool = False) -> None:
        """Load data in the background. Uses cache unless ``force``."""
        if self._is_destroyed:
            return

        generation = bump_generation(self)
        key = self.cache_key()

        # Instant paint from cache
        if not force and key:
            cached = data_cache.get(key)
            if cached is not None:
                try:
                    self.apply_data(cached)
                    self._has_applied_data = True
                    self.hide_loading()
                    hide_global_nav_loading(self)
                except Exception as exc:
                    logger.debug("cache apply failed: %s", exp if False else exc)
                # Still revalidate in background
                self._start_fetch(generation, key, soft=True)
                return

        if not self._has_applied_data:
            self.show_loading()
        self._start_fetch(generation, key, soft=False)

    def soft_refresh(self) -> None:
        """Background refresh preferring cache – used when navigating back."""
        self.refresh(force=False)

    def _start_fetch(self, generation: int, key: Optional[str], soft: bool) -> None:
        def fetch() -> Any:
            def do_load() -> Any:
                return self.load_data()

            if key:
                if soft:
                    # Revalidate: always hit network, then update cache
                    value = do_load()
                    data_cache.set(key, value, ttl=self.CACHE_TTL)
                    return value
                return data_cache.get_or_fetch(key, do_load, ttl=self.CACHE_TTL)
            return do_load()

        def apply(data: Any) -> None:
            if self._is_destroyed:
                return
            if current_generation(self) != generation:
                return
            self.hide_loading()
            self.clear_error()
            try:
                self.apply_data(data)
                self._has_applied_data = True
            except Exception as exc:
                logger.exception("apply_data failed")
                self.on_load_error(exc)

        def failed(exc: Exception) -> None:
            if self._is_destroyed or current_generation(self) != generation:
                return
            self.hide_loading()
            # Keep showing cached UI if we already painted
            if not self._has_applied_data:
                self.on_load_error(exc)

        run_in_background(
            self,
            fetch,
            apply,
            failed,
            name=f"{self.PAGE_TITLE}-load",
            generation=generation,
        )

    def on_show(self) -> None:
        """Called when this view becomes the active workspace page."""
        self.soft_refresh()

    def on_hide(self) -> None:
        """Called when navigating away – invalidate in-flight loads."""
        bump_generation(self)

    # ------------------------------------------------------------------ loading / error
    def show_loading(self, message: str = "Loading…") -> None:
        if self._is_destroyed:
            return
        try:
            if self._loading_overlay is None:
                ov = ctk.CTkFrame(self, fg_color=Theme.BG, corner_radius=0)
                card = ctk.CTkFrame(
                    ov,
                    fg_color=Theme.PANEL,
                    corner_radius=12,
                    border_width=1,
                    border_color=getattr(Theme, "BORDER", "#E5E7EB"),
                    width=280,
                    height=100,
                )
                card.place(relx=0.5, rely=0.4, anchor="center")
                card.pack_propagate(False)
                self._loading_label = ctk.CTkLabel(
                    card,
                    text=message,
                    font=("Segoe UI", 13, "bold"),
                    text_color=Theme.TEXT,
                )
                self._loading_label.pack(expand=True)
                self._loading_overlay = ov
            else:
                self._loading_label.configure(text=message)
            self._loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._loading_overlay.lift()
        except Exception as exc:
            logger.debug("show_loading failed: %s", exc)

    def hide_loading(self) -> None:
        try:
            hide_global_nav_loading(self)
        except Exception:
            pass
        ov = self._loading_overlay
        if ov is not None:
            try:
                ov.place_forget()
            except Exception:
                pass

    def show_error(self, message: str) -> None:
        if self._is_destroyed:
            return
        try:
            if self._error_banner is None:
                self._error_banner = ctk.CTkFrame(
                    self, fg_color="#FEE2E2", corner_radius=8, height=36
                )
                self._error_label = ctk.CTkLabel(
                    self._error_banner,
                    text=message,
                    text_color="#991B1B",
                    font=("Segoe UI", 12),
                    anchor="w",
                )
                self._error_label.pack(fill="x", padx=12, pady=8)
            else:
                self._error_label.configure(text=message)
            self._error_banner.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 8))
        except Exception as exc:
            logger.debug("show_error failed: %s", exc)

    def clear_error(self) -> None:
        banner = self._error_banner
        if banner is not None:
            try:
                banner.grid_forget()
            except Exception:
                pass

    def safe_after(self, ms: int, callback: Callable[[], None]) -> Optional[Any]:
        if self._is_destroyed:
            return None

        def wrapped() -> None:
            if self._is_destroyed:
                return
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return
            try:
                callback()
            except Exception:
                logger.exception("safe_after callback failed")

        try:
            job = self.after(ms, wrapped)
            self._after_jobs.append(job)
            return job
        except Exception:
            return None

    def cancel_after_jobs(self) -> None:
        for job in list(self._after_jobs):
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._after_jobs.clear()

    def destroy(self) -> None:
        self._is_destroyed = True
        bump_generation(self)
        self.cancel_after_jobs()
        try:
            super().destroy()
        except Exception:
            pass
