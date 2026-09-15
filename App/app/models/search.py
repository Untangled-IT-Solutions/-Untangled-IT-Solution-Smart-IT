"""Global search view model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    """A lightweight result from a cross-module backend search."""

    source: str
    title: str
    detail: str
    reference_id: int | None
