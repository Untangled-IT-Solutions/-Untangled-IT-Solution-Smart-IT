"""Load and cache CTkImage / PhotoImage once – never resize on every navigation."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional, Tuple

_lock = threading.Lock()
_cache: dict[Tuple[str, int, int], Any] = {}


def get_ctk_image(path: str | Path, size: Tuple[int, int] = (32, 32)) -> Optional[Any]:
    key_path = str(path)
    key = (key_path, int(size[0]), int(size[1]))
    with _lock:
        if key in _cache:
            return _cache[key]
    p = Path(key_path)
    if not p.is_file():
        return None
    try:
        from PIL import Image
        import customtkinter as ctk

        img = Image.open(p)
        img = img.convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        with _lock:
            _cache[key] = ctk_img
        return ctk_img
    except Exception:
        return None


def clear() -> None:
    with _lock:
        _cache.clear()
