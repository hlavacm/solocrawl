"""Search provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from solocrawl.core.models import SearchResult


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol for federated web search providers."""

    name: str
    zero_config: bool

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Run a search query and return normalized results."""
        ...
