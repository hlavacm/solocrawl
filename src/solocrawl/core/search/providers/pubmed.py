"""PubMed search provider via NCBI E-utilities."""

from __future__ import annotations

import logging

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search.registry import register

logger = logging.getLogger(__name__)

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@register("pubmed", configurable=True)
class PubMedProvider:
    """Search PubMed via NCBI E-utilities."""

    name = "pubmed"
    zero_config = False

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        stripped = query.strip()
        if not stripped:
            return []

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            search_response = await client.get(
                f"{_EUTILS_BASE}/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": stripped,
                    "retmode": "json",
                    "retmax": str(max(1, limit)),
                },
            )
            search_response.raise_for_status()
            search_payload = search_response.json()
            ids = _extract_ids(search_payload, limit=limit)
            if not ids:
                return []

            summary_response = await client.get(
                f"{_EUTILS_BASE}/esummary.fcgi",
                params={
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "retmode": "json",
                },
            )
            summary_response.raise_for_status()
            summary_payload = summary_response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("pubmed search failed for %r: %s", stripped, exc)
            return []

        return _parse_pubmed_summary(summary_payload, ids=ids)


def _extract_ids(payload: object, *, limit: int) -> list[str]:
    if not isinstance(payload, dict):
        return []
    esearch = payload.get("esearchresult")
    if not isinstance(esearch, dict):
        return []
    idlist = esearch.get("idlist")
    if not isinstance(idlist, list):
        return []
    return [str(item) for item in idlist[:limit]]


def _parse_pubmed_summary(payload: object, *, ids: list[str]) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []

    results: list[SearchResult] = []
    for pubmed_id in ids:
        item = result.get(pubmed_id)
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        source = item.get("source", "")
        pubdate = item.get("pubdate", "")
        snippet_parts = [part for part in (source, pubdate) if isinstance(part, str) and part]
        snippet = " · ".join(snippet_parts)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"
        results.append(
            SearchResult(
                title=title.strip(),
                url=url,
                snippet=snippet,
                source="pubmed",
                raw=item,
            )
        )
    return results
