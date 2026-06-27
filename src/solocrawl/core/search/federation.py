"""Run multiple search providers and merge their results."""

from __future__ import annotations

import asyncio
import logging

from solocrawl.core.models import SearchResult
from solocrawl.core.search.fusion import fuse_results
from solocrawl.core.search.protocol import SearchProvider

logger = logging.getLogger(__name__)


async def federated_search(
    providers: list[SearchProvider],
    query: str,
    *,
    limit: int = 5,
) -> list[SearchResult]:
    """Search across providers in parallel and return a fused result list."""
    if not providers or limit <= 0:
        return []

    per_provider_limit = max(limit, limit * len(providers))
    tasks = [provider.search(query, limit=per_provider_limit) for provider in providers]
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    provider_results: list[tuple[str, list[SearchResult]]] = []
    for provider, outcome in zip(providers, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            logger.warning(
                "search provider %r failed for query %r: %s",
                provider.name,
                query,
                outcome,
            )
            continue

        if not isinstance(outcome, list):
            logger.warning(
                "search provider %r returned unexpected type for query %r: %s",
                provider.name,
                query,
                type(outcome).__name__,
            )
            continue

        provider_results.append((provider.name, outcome))

    return fuse_results(provider_results, limit=limit)
