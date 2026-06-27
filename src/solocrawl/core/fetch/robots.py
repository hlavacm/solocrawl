"""robots.txt fetching and enforcement.

Polite, fail-open enforcement: a missing, forbidden, or unreachable robots.txt is
treated as "allowed" (this is a small individual-developer tool, not a crawler).
Parsed robots files are cached per host for the life of the process.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

_ROBOTS_TIMEOUT = 5.0
_MAX_CACHE_ENTRIES = 512

_cache: dict[str, RobotFileParser] = {}
_lock = asyncio.Lock()


class RobotsDisallowedError(Exception):
    """Raised when a host's robots.txt disallows fetching a URL."""


def _base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _allow_all_parser() -> RobotFileParser:
    parser = RobotFileParser()
    parser.parse([])  # no rules -> everything allowed
    return parser


async def _load_parser(base: str, *, client: httpx.AsyncClient) -> RobotFileParser:
    robots_url = f"{base}/robots.txt"
    try:
        response = await client.get(robots_url, timeout=_ROBOTS_TIMEOUT, follow_redirects=False)
    except httpx.HTTPError as exc:
        logger.debug("robots.txt fetch failed for %s: %s (allowing)", base, exc)
        return _allow_all_parser()

    if not response.is_success:
        # Missing, forbidden, or redirected robots.txt -> allow (fail-open).
        # Not following redirects also closes an SSRF vector via a crafted robots.txt.
        return _allow_all_parser()

    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser


async def is_fetch_allowed(url: str, *, user_agent: str, client: httpx.AsyncClient) -> bool:
    """Return whether ``url`` may be fetched per the host's robots.txt (fail-open)."""
    base = _base_url(url)
    parser = _cache.get(base)
    if parser is None:
        async with _lock:
            parser = _cache.get(base)
            if parser is None:
                parser = await _load_parser(base, client=client)
                if base not in _cache and len(_cache) >= _MAX_CACHE_ENTRIES:
                    del _cache[next(iter(_cache))]
                _cache[base] = parser
    return parser.can_fetch(user_agent, url)


def reset_robots_cache() -> None:
    """Clear the robots.txt cache. Intended for tests only."""
    _cache.clear()


__all__ = ["RobotsDisallowedError", "is_fetch_allowed", "reset_robots_cache"]
