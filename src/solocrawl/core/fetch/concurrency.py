"""Bounded concurrency for fetch operations (global + per-domain)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from solocrawl.config import ConcurrencyConfig

_global_semaphore: asyncio.Semaphore | None = None
_global_semaphore_limit: int | None = None
_domain_semaphores: dict[str, asyncio.Semaphore] = {}
_domain_limits: dict[str, int] = {}
_state_lock = asyncio.Lock()


async def _get_global_semaphore(limit: int) -> asyncio.Semaphore:
    global _global_semaphore, _global_semaphore_limit
    async with _state_lock:
        if _global_semaphore is None or _global_semaphore_limit != limit:
            _global_semaphore = asyncio.Semaphore(limit)
            _global_semaphore_limit = limit
        return _global_semaphore


async def _get_domain_semaphore(domain: str, limit: int) -> asyncio.Semaphore:
    async with _state_lock:
        current_limit = _domain_limits.get(domain)
        semaphore = _domain_semaphores.get(domain)
        if semaphore is None or current_limit != limit:
            _domain_semaphores[domain] = asyncio.Semaphore(limit)
            _domain_limits[domain] = limit
            semaphore = _domain_semaphores[domain]
        return semaphore


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower() or "unknown"


@asynccontextmanager
async def acquire_fetch_slots(url: str, config: ConcurrencyConfig) -> AsyncIterator[None]:
    """Acquire global and per-domain fetch slots for a URL."""
    global_sem = await _get_global_semaphore(config.max_concurrent_fetches)
    domain_sem = await _get_domain_semaphore(
        _domain_from_url(url),
        config.per_domain_limit,
    )
    async with global_sem, domain_sem:
        yield


async def reset_concurrency_state() -> None:
    """Reset semaphore state (for tests)."""
    global _global_semaphore, _global_semaphore_limit
    async with _state_lock:
        _global_semaphore = None
        _global_semaphore_limit = None
        _domain_semaphores.clear()
        _domain_limits.clear()
