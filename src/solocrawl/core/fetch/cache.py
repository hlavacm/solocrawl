"""Lightweight in-memory TTL cache for fetch results.

Disabled by default (``SOLOCRAWL_CACHE_TTL_SECONDS=0``). In-process only — it keeps
the "one shared client per process" model and mainly benefits the long-lived MCP
server and multi-URL operations (research/batch) within a single run.
"""

from __future__ import annotations

import time

from solocrawl.core.models import FetchResult

_MAX_ENTRIES = 256

_cache: dict[str, tuple[float, FetchResult]] = {}


def cache_get(url: str) -> FetchResult | None:
    """Return a non-expired cached result for ``url`` (or ``None``)."""
    entry = _cache.get(url)
    if entry is None:
        return None
    expires_at, result = entry
    if time.monotonic() >= expires_at:
        _cache.pop(url, None)
        return None
    return result


def cache_set(url: str, result: FetchResult, ttl_seconds: float) -> None:
    """Store ``result`` for ``url`` with a TTL. A non-positive TTL stores nothing."""
    if ttl_seconds <= 0:
        return
    if url not in _cache:
        while len(_cache) >= _MAX_ENTRIES:
            # Evict the oldest entry instead of dropping the whole cache.
            del _cache[next(iter(_cache))]
    _cache[url] = (time.monotonic() + ttl_seconds, result)


def reset_cache() -> None:
    """Clear the fetch cache. Intended for tests only."""
    _cache.clear()


__all__ = ["cache_get", "cache_set", "reset_cache"]
