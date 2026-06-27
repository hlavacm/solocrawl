"""Wikidata search provider."""

from __future__ import annotations

import logging

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)


@register("wikidata")
class WikidataProvider:
    """Search Wikidata entities via the MediaWiki API."""

    name = "wikidata"
    zero_config = False

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        stripped = query.strip()
        if not stripped:
            return []

        params = {
            "action": "wbsearchentities",
            "search": stripped,
            "language": "en",
            "format": "json",
            "limit": str(max(1, limit)),
        }
        url = "https://www.wikidata.org/w/api.php"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("wikidata search failed for %r: %s", stripped, exc)
            return []

        return _parse_wikidata_payload(payload, limit=limit)


def _parse_wikidata_payload(payload: object, *, limit: int) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("search")
    if not isinstance(items, list):
        return []

    results: list[SearchResult] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            continue
        description = item.get("description", "")
        snippet = description if isinstance(description, str) else ""
        entity_url = item.get("url", "")
        if isinstance(entity_url, str) and entity_url.startswith("//"):
            entity_url = f"https:{entity_url}"
        elif not isinstance(entity_url, str) or not entity_url:
            entity_id = item.get("id", "")
            entity_url = f"https://www.wikidata.org/wiki/{entity_id}"

        results.append(
            SearchResult(
                title=label,
                url=entity_url,
                snippet=snippet,
                source="wikidata",
                raw=item,
            )
        )
    return results
