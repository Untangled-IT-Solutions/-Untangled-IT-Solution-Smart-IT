"""Base presenter – business orchestration, no Tk widgets."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("untangled.presenter")


class BasePresenter:
    """Coordinates services for a feature. Views call presenters; presenters never import views."""

    def __init__(self) -> None:
        self._disposed = False

    def dispose(self) -> None:
        self._disposed = True

    @property
    def disposed(self) -> bool:
        return self._disposed
