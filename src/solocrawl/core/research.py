"""Combined research: federated search, then scrape the top results and aggregate.

Pure retrieval + concatenation with citations — no embeddings or ranking models
(see the project non-goals). Reuses the search federation and the fetch path, so it
inherits robots.txt enforcement, bounded concurrency, and the optional cache.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from solocrawl.config import Config, load_config
from solocrawl.core.fetch import fetch
from solocrawl.core.proxy import redact_proxy_credentials
from solocrawl.core.search import federated_search, select_providers

logger = logging.getLogger(__name__)

MAX_RESEARCH_DEPTH = 8


@dataclass
class ResearchDocument:
    """One researched source: a search hit plus its scraped content (or an error)."""

    title: str
    url: str
    source: str
    content: str | None = None
    error: str | None = None


async def research(
    query: str,
    *,
    depth: int = 3,
    config: Config | None = None,
) -> list[ResearchDocument]:
    """Search for ``query`` and scrape the top ``depth`` results into documents."""
    cfg = load_config() if config is None else config
    stripped = query.strip()
    if not stripped:
        return []

    depth = min(max(1, depth), MAX_RESEARCH_DEPTH)
    providers = select_providers(cfg)
    results = await federated_search(providers, stripped, limit=depth)
    top = results[:depth]
    if not top:
        return []

    fetched = await asyncio.gather(
        *(fetch(result.url, config=cfg) for result in top),
        return_exceptions=True,
    )

    documents: list[ResearchDocument] = []
    for result, outcome in zip(top, fetched, strict=True):
        if isinstance(outcome, BaseException):
            message = redact_proxy_credentials(str(outcome), cfg.proxy)
            logger.warning("research fetch failed for %s: %s", result.url, message)
            documents.append(
                ResearchDocument(
                    title=result.title,
                    url=result.url,
                    source=result.source,
                    content=None,
                    error=message,
                )
            )
        else:
            documents.append(
                ResearchDocument(
                    title=result.title,
                    url=result.url,
                    source=result.source,
                    content=outcome.content,
                )
            )
    return documents


def research_to_markdown(query: str, documents: list[ResearchDocument]) -> str:
    """Aggregate research documents into a single cited markdown report."""
    if not documents:
        return f"# Research: {query}\n\nNo results."

    blocks = [f"# Research: {query}"]
    for index, doc in enumerate(documents, start=1):
        section = [
            f"## {index}. {doc.title}",
            f"Source: {doc.source} — {doc.url}",
            "",
        ]
        if doc.content:
            section.append(doc.content.strip())
        else:
            section.append(f"_[fetch failed: {doc.error}]_")
        blocks.append("\n".join(section))
    return "\n\n---\n\n".join(blocks)


__all__ = ["ResearchDocument", "research", "research_to_markdown"]
