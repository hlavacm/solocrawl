"""MDN Web Docs search provider (opt-in)."""

from __future__ import annotations

import logging

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)

_MDN_BASE = "https://developer.mozilla.org"


@register("mdn")
class MdnProvider:
    """Search MDN Web Docs via its public search API."""

    name = "mdn"
    zero_config = False

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        stripped = query.strip()
        if not stripped:
            return []

        params = {"q": stripped, "locale": "en-US"}
        url = f"{_MDN_BASE}/api/v1/search"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("mdn search failed for %r: %s", stripped, exc)
            return []

        return _parse_mdn_payload(payload, limit=limit)


def _parse_mdn_payload(payload: object, *, limit: int) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []
    documents = payload.get("documents")
    if not isinstance(documents, list):
        return []

    results: list[SearchResult] = []
    for doc in documents[:limit]:
        if not isinstance(doc, dict):
            continue
        title = doc.get("title")
        mdn_url = doc.get("mdn_url")
        if not isinstance(title, str) or not isinstance(mdn_url, str):
            continue
        summary = doc.get("summary")
        snippet = summary.strip() if isinstance(summary, str) else ""
        score_raw = doc.get("score", 0)
        score = float(score_raw) if isinstance(score_raw, int | float) else 0.0
        results.append(
            SearchResult(
                title=title.strip(),
                url=_absolute_url(mdn_url.strip()),
                snippet=snippet,
                source="mdn",
                score=score,
                raw=doc,
            )
        )
    return results


def _absolute_url(mdn_url: str) -> str:
    if mdn_url.startswith("http://") or mdn_url.startswith("https://"):
        return mdn_url
    return f"{_MDN_BASE}{mdn_url}"
