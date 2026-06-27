"""Reciprocal Rank Fusion and URL deduplication for search results."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from solocrawl.core.models import SearchResult

RRF_K = 60

_TRACKING_QUERY_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
)


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication across providers."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY_PARAMS
    ]
    query = urlencode(sorted(filtered_query))

    return urlunparse((scheme, netloc, path, "", query, ""))


def fuse_results(
    provider_results: Iterable[tuple[str, list[SearchResult]]],
    *,
    limit: int,
    k: int = RRF_K,
) -> list[SearchResult]:
    """Merge provider result lists with RRF scoring and URL deduplication."""
    scores: dict[str, float] = {}
    merged: dict[str, SearchResult] = {}
    sources: dict[str, set[str]] = {}

    for provider_name, results in provider_results:
        for rank, result in enumerate(results, start=1):
            normalized = normalize_url(result.url)
            scores[normalized] = scores.get(normalized, 0.0) + (1.0 / (k + rank))
            sources.setdefault(normalized, set()).add(provider_name)

            existing = merged.get(normalized)
            if existing is None or _is_better_candidate(result, existing):
                merged[normalized] = result

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    fused: list[SearchResult] = []

    for normalized, score in ranked[: max(0, limit)]:
        result = merged[normalized]
        source_names = sorted(sources[normalized])
        source_label = result.source
        if len(source_names) > 1:
            source_label = "+".join(source_names)

        fused.append(
            SearchResult(
                title=result.title,
                url=result.url,
                snippet=result.snippet,
                source=source_label,
                score=score,
                raw=result.raw,
            )
        )

    return fused


def _is_better_candidate(candidate: SearchResult, existing: SearchResult) -> bool:
    if len(candidate.snippet) != len(existing.snippet):
        return len(candidate.snippet) > len(existing.snippet)
    return candidate.title >= existing.title
