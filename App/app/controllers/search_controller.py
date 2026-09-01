"""Global search controller."""

from app.models.search import SearchResult
from app.services.search_service import SearchService


class SearchController:
    """Keeps cross-module database searching out of the header view."""

    def __init__(self, search_service: SearchService) -> None:
        self._search_service = search_service

    def search(self, query: str) -> list[SearchResult]:
        return self._search_service.search(query)
