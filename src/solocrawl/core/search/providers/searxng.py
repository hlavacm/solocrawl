"""SearXNG meta-search provider (opt-in, self-hosted)."""

from __future__ import annotations

import logging
import os

import httpx

from solocrawl.config import Config, init_env, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)

_BASE_URL_ENV = "SOLOCRAWL_SEARXNG_URL"


@register("searxng", required_env_key=_BASE_URL_ENV)
class SearxngProvider:
    """Query a self-hosted SearXNG instance's JSON search API."""

    name = "searxng"
    zero_config = False

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        stripped = query.strip()
        if not stripped:
            return []

        base = _base_url()
        if base is None:
            logger.warning("searxng search skipped: %s is not set", _BASE_URL_ENV)
            return []

        params = {"q": stripped, "format": "json"}
        url = f"{base}/search"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("searxng search failed for %r: %s", stripped, exc)
            return []

        return _parse_searxng_payload(payload, limit=limit)


def _base_url() -> str | None:
    init_env()
    raw = os.environ.get(_BASE_URL_ENV)
    if raw is None or not raw.strip():
        return None
    return raw.strip().rstrip("/")


def _parse_searxng_payload(payload: object, *, limit: int) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []
    results_raw = payload.get("results")
    if not isinstance(results_raw, list):
        return []

    results: list[SearchResult] = []
    for item in results_raw[:limit]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        content = item.get("content")
        snippet = content.strip() if isinstance(content, str) else ""
        score_raw = item.get("score", 0)
        score = float(score_raw) if isinstance(score_raw, int | float) else 0.0
        results.append(
            SearchResult(
                title=title.strip(),
                url=url.strip(),
                snippet=snippet,
                source="searxng",
                score=score,
                raw=item,
            )
        )
    return results
