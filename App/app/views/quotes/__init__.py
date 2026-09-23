"""Quote Management feature package.

Split from the former god-file ``quote_management_view.py``:

  constants.py   – status workflow, colors, role lists
  formatting.py  – pure helpers (dates, money, assignment checks)
Public entry (compatible with navigation factory):
  ``from app.views.quote_management_view import QuoteManagementView``
"""

from app.views.quotes.constants import (
    STATUS_OPTIONS,
    STATUS_COLORS,
    STATUS_ICONS,
    MANAGER_ROLES,
    STAFF_ROLES,
)

__all__ = [
    "STATUS_OPTIONS",
    "STATUS_COLORS",
    "STATUS_ICONS",
    "MANAGER_ROLES",
    "STAFF_ROLES",
]
