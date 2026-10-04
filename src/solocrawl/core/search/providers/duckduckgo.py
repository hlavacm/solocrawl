"""DuckDuckGo search provider via the ddgs package."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from solocrawl.config import Config, load_config
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)


def _import_ddgs() -> Any:
    try:
        from ddgs import DDGS
    except ImportError:
        import importlib

        try:
            module = importlib.import_module("duckduckgo_search")
        except ImportError as exc:
            msg = "ddgs package is not installed"
            raise ImportError(msg) from exc
        DDGS = module.DDGS
    return DDGS


def _run_ddgs_text(query: str, *, limit: int, timeout: float = 30.0) -> list[dict[str, Any]]:
    ddgs_cls = _import_ddgs()
    ddgs = ddgs_cls(timeout=timeout)
    raw_results = ddgs.text(query, max_results=limit)
    if not isinstance(raw_results, list):
        return []
    return [item for item in raw_results if isinstance(item, dict)]


def _map_ddgs_results(raw_results: list[dict[str, Any]], *, limit: int) -> list[SearchResult]:
    results: list[SearchResult] = []
    for item in raw_results[:limit]:
        title = item.get("title", "")
        url = item.get("href") or item.get("url") or ""
        snippet = item.get("body") or item.get("snippet") or ""
        if not isinstance(title, str) or not isinstance(url, str) or not isinstance(snippet, str):
            continue
        if not title.strip() or not url.strip():
            continue
        results.append(
            SearchResult(
                title=title.strip(),
                url=url.strip(),
                snippet=snippet.strip(),
                source="duckduckgo",
                raw=item,
            )
        )
    return results


@register("duckduckgo", zero_config=True, configurable=True)
class DuckDuckGoProvider:
    """Search the web via DuckDuckGo using the ddgs package."""

    name = "duckduckgo"
    zero_config = True

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Search DuckDuckGo without blocking the event loop."""
        stripped = query.strip()
        if not stripped:
            return []

        try:
            raw_results = await asyncio.to_thread(
                _run_ddgs_text,
                stripped,
                limit=max(1, limit),
                timeout=self._config.concurrency.timeout_seconds,
            )
        except Exception as exc:
            logger.warning("duckduckgo search failed for %r: %s", stripped, exc)
            return []

        return _map_ddgs_results(raw_results, limit=limit)
