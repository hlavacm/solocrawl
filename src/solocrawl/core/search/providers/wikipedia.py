"""Wikipedia search provider via the MediaWiki Action API."""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import quote

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)

_SEARCH_MATCH_RE = re.compile(r"<span class=\"searchmatch\">(.*?)</span>", re.IGNORECASE)


@register("wikipedia", zero_config=True)
class WikipediaProvider:
    """Search English Wikipedia using the official MediaWiki API."""

    name = "wikipedia"
    zero_config = True

    def __init__(
        self,
        *,
        wiki: str = "en",
        config: Config | None = None,
    ) -> None:
        self._wiki = wiki
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Search Wikipedia and return normalized results."""
        stripped = query.strip()
        if not stripped:
            return []

        params = {
            "action": "query",
            "list": "search",
            "srsearch": stripped,
            "srlimit": str(max(1, limit)),
            "format": "json",
            "origin": "*",
        }
        url = f"https://{self._wiki}.wikipedia.org/w/api.php"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("wikipedia search failed for %r: %s", stripped, exc)
            return []

        return _parse_search_response(payload, wiki=self._wiki, limit=limit)


def _parse_search_response(
    payload: object,
    *,
    wiki: str,
    limit: int,
) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []

    query_block = payload.get("query")
    if not isinstance(query_block, dict):
        return []

    search_items = query_block.get("search")
    if not isinstance(search_items, list):
        return []

    results: list[SearchResult] = []
    for item in search_items[:limit]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            continue

        snippet_raw = item.get("snippet", "")
        snippet = _clean_snippet(snippet_raw if isinstance(snippet_raw, str) else "")

        results.append(
            SearchResult(
                title=title,
                url=_article_url(title, wiki=wiki),
                snippet=snippet,
                source="wikipedia",
                raw=item,
            )
        )

    return results


def _clean_snippet(snippet: str) -> str:
    unescaped = html.unescape(snippet)
    without_tags = re.sub(r"<[^>]+>", "", unescaped)

    def highlight_replacer(match: re.Match[str]) -> str:
        return match.group(1)

    cleaned = _SEARCH_MATCH_RE.sub(highlight_replacer, without_tags)
    return " ".join(cleaned.split())


def _article_url(title: str, *, wiki: str) -> str:
    slug = quote(title.replace(" ", "_"), safe="()")
    return f"https://{wiki}.wikipedia.org/wiki/{slug}"
