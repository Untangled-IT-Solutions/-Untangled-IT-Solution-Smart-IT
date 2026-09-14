"""Compatibility shim – Quote Management lives in ``app.views.quotes``.

Navigation and older imports should keep using:

    from app.views.quote_management_view import QuoteManagementView

Implementation: ``app.views.quotes.view.QuoteManagementView``
Constants:      ``app.views.quotes.constants``
Helpers:        ``app.views.quotes.formatting``
"""

from app.views.quotes.view import QuoteManagementView

__all__ = ["QuoteManagementView"]
