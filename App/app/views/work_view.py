"""Compatibility imports for the retired Work view.

Production navigation uses :class:`TaskView` for Work and
:class:`QuoteManagementView` for quote operations.  Keeping these aliases
preserves older imports without retaining a second data-access implementation.
"""

from app.views.quote_management_view import QuoteManagementView
from app.views.task_view import TaskView

WorkView = TaskView

__all__ = ["QuoteManagementView", "TaskView", "WorkView"]
