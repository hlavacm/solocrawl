"""Hacker News search provider via Algolia."""

from __future__ import annotations

import logging

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)


@register("hackernews")
class HackerNewsProvider:
    """Search Hacker News posts via the Algolia API."""

    name = "hackernews"
    zero_config = False

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        stripped = query.strip()
        if not stripped:
            return []

        params = {"query": stripped, "hitsPerPage": str(max(1, limit))}
        url = "https://hn.algolia.com/api/v1/search"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("hackernews search failed for %r: %s", stripped, exc)
            return []

        return _parse_hn_payload(payload, limit=limit)


def _parse_hn_payload(payload: object, *, limit: int) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []
    hits = payload.get("hits")
    if not isinstance(hits, list):
        return []

    results: list[SearchResult] = []
    for hit in hits[:limit]:
        if not isinstance(hit, dict):
            continue
        title = hit.get("title")
        url = hit.get("url") or hit.get("story_url")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        snippet_raw = hit.get("story_text") or hit.get("comment_text") or ""
        snippet = snippet_raw if isinstance(snippet_raw, str) else ""
        points = hit.get("points", 0)
        score = float(points) if isinstance(points, int | float) else 0.0
        results.append(
            SearchResult(
                title=title.strip(),
                url=url.strip(),
                snippet=snippet.strip(),
                source="hackernews",
                score=score,
                raw=hit,
            )
        )
    return results
