"""StackExchange search provider via the official API."""

from __future__ import annotations

import html
import logging
import re

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)

_API_BASE = "https://api.stackexchange.com/2.3"
_BODY_FILTER = "withbody"


@register("stackexchange", zero_config=True, configurable=True)
class StackExchangeProvider:
    """Search Stack Overflow and sibling sites via the StackExchange API."""

    name = "stackexchange"
    zero_config = True

    def __init__(
        self,
        *,
        site: str = "stackoverflow",
        config: Config | None = None,
    ) -> None:
        self._site = site
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Search StackExchange and return normalized results."""
        stripped = query.strip()
        if not stripped:
            return []

        params: dict[str, str | int] = {
            "order": "desc",
            "sort": "relevance",
            "q": stripped,
            "site": self._site,
            "pagesize": max(1, limit),
            "filter": _BODY_FILTER,
        }

        api_key = self._config_env_key()
        if api_key is not None:
            params["key"] = api_key

        url = f"{_API_BASE}/search/advanced"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("stackexchange search failed for %r: %s", stripped, exc)
            return []

        return _parse_search_response(payload, limit=limit)

    def _config_env_key(self) -> str | None:
        import os

        value = os.environ.get("SOLOCRAWL_STACKEXCHANGE_KEY")
        if value is None or value.strip() == "":
            return None
        return value.strip()


def _parse_search_response(payload: object, *, limit: int) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []

    items = payload.get("items")
    if not isinstance(items, list):
        return []

    results: list[SearchResult] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue

        title = item.get("title")
        link = item.get("link")
        if not isinstance(title, str) or not isinstance(link, str):
            continue
        if not title.strip() or not link.strip():
            continue

        body_raw = item.get("body", "")
        snippet = _snippet_from_body(body_raw if isinstance(body_raw, str) else "")
        score_raw = item.get("score", 0)
        score = float(score_raw) if isinstance(score_raw, int | float) else 0.0

        results.append(
            SearchResult(
                title=title.strip(),
                url=link.strip(),
                snippet=snippet,
                source="stackexchange",
                score=score,
                raw=item,
            )
        )

    return results


def _snippet_from_body(body: str, *, max_length: int = 280) -> str:
    if not body.strip():
        return ""

    unescaped = html.unescape(body)
    without_tags = re.sub(r"<[^>]+>", " ", unescaped)
    collapsed = " ".join(without_tags.split())
    if len(collapsed) <= max_length:
        return collapsed
    return collapsed[: max_length - 3].rstrip() + "..."
