"""Reddit search provider (opt-in)."""

from __future__ import annotations

import logging

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)

_REDDIT_BASE = "https://www.reddit.com"
_SNIPPET_LIMIT = 300


@register("reddit")
class RedditProvider:
    """Search Reddit posts via the public JSON search endpoint."""

    name = "reddit"
    zero_config = False

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        stripped = query.strip()
        if not stripped:
            return []

        params = {"q": stripped, "limit": str(max(1, limit))}
        url = f"{_REDDIT_BASE}/search.json"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("reddit search failed for %r: %s", stripped, exc)
            return []

        return _parse_reddit_payload(payload, limit=limit)


def _parse_reddit_payload(payload: object, *, limit: int) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    children = data.get("children")
    if not isinstance(children, list):
        return []

    results: list[SearchResult] = []
    for child in children[:limit]:
        if not isinstance(child, dict):
            continue
        post = child.get("data")
        if not isinstance(post, dict):
            continue
        title = post.get("title")
        permalink = post.get("permalink")
        if not isinstance(title, str) or not isinstance(permalink, str):
            continue
        selftext = post.get("selftext")
        snippet = selftext.strip()[:_SNIPPET_LIMIT] if isinstance(selftext, str) else ""
        score_raw = post.get("score", 0)
        score = float(score_raw) if isinstance(score_raw, int | float) else 0.0
        results.append(
            SearchResult(
                title=title.strip(),
                url=f"{_REDDIT_BASE}{permalink}",
                snippet=snippet,
                source="reddit",
                score=score,
                raw=post,
            )
        )
    return results
