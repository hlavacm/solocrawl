"""GitHub repository search provider (opt-in)."""

from __future__ import annotations

import logging

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)

_HEADERS = {"Accept": "application/vnd.github+json"}


@register("github", configurable=True)
class GitHubProvider:
    """Search public GitHub repositories via the REST search API."""

    name = "github"
    zero_config = False

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        stripped = query.strip()
        if not stripped:
            return []

        params = {"q": stripped, "per_page": str(max(1, limit))}
        url = "https://api.github.com/search/repositories"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params, headers=_HEADERS)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("github search failed for %r: %s", stripped, exc)
            return []

        return _parse_github_payload(payload, limit=limit)


def _parse_github_payload(payload: object, *, limit: int) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []

    results: list[SearchResult] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        full_name = item.get("full_name")
        html_url = item.get("html_url")
        if not isinstance(full_name, str) or not isinstance(html_url, str):
            continue
        description = item.get("description")
        snippet = description.strip() if isinstance(description, str) else ""
        stars = item.get("stargazers_count", 0)
        score = float(stars) if isinstance(stars, int | float) else 0.0
        results.append(
            SearchResult(
                title=full_name.strip(),
                url=html_url.strip(),
                snippet=snippet,
                source="github",
                score=score,
                raw=item,
            )
        )
    return results
