"""arXiv search provider."""

from __future__ import annotations

import logging

# Stdlib ElementTree is used deliberately: it does not resolve external entities,
# so the arXiv Atom feed cannot trigger XXE.
import xml.etree.ElementTree as ET

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


@register("arxiv")
class ArxivProvider:
    """Search arXiv preprints via the official Atom API."""

    name = "arxiv"
    zero_config = False

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        stripped = query.strip()
        if not stripped:
            return []

        params = {
            "search_query": f"all:{stripped}",
            "start": "0",
            "max_results": str(max(1, limit)),
        }
        url = "https://export.arxiv.org/api/query"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, params=params)
            response.raise_for_status()
            body = response.text
        except httpx.HTTPError as exc:
            logger.warning("arxiv search failed for %r: %s", stripped, exc)
            return []

        return _parse_arxiv_atom(body, limit=limit)


def _parse_arxiv_atom(body: str, *, limit: int) -> list[SearchResult]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []

    results: list[SearchResult] = []
    for entry in root.findall("atom:entry", _ATOM_NS)[:limit]:
        title_el = entry.find("atom:title", _ATOM_NS)
        summary_el = entry.find("atom:summary", _ATOM_NS)
        link_el = entry.find("atom:link[@rel='alternate']", _ATOM_NS)
        if link_el is None:
            link_el = entry.find("atom:id", _ATOM_NS)

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        url = link_el.get("href") if link_el is not None and link_el.get("href") else ""
        if url == "" and link_el is not None and link_el.text:
            url = link_el.text.strip()
        snippet = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
        if not title or not url:
            continue

        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source="arxiv",
                raw={"title": title, "url": url, "summary": snippet},
            )
        )
    return results
