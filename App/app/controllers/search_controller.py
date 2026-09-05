"""Search controller stub (search will be wired to backend later)."""

class SearchController:
    def __init__(self, search_service=None) -> None:
        self._service = search_service

    def search(self, query: str = "") -> list:
        return []
