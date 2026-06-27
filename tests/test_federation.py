"""Tests for federated search and RRF fusion."""

from __future__ import annotations

import pytest

from solocrawl.core.models import SearchResult
from solocrawl.core.search.federation import federated_search
from solocrawl.core.search.fusion import fuse_results, normalize_url


class ProviderA:
    name = "provider_a"
    zero_config = True

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title="Alpha",
                url="https://example.com/a/",
                snippet="first",
                source=self.name,
            ),
            SearchResult(
                title="Shared",
                url="https://example.com/shared?utm_source=a",
                snippet="shared from a",
                source=self.name,
            ),
        ][:limit]


class ProviderB:
    name = "provider_b"
    zero_config = True

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title="Beta",
                url="https://example.com/b",
                snippet="second",
                source=self.name,
            ),
            SearchResult(
                title="Shared duplicate",
                url="https://example.com/shared/",
                snippet="shared from b with longer snippet text",
                source=self.name,
            ),
        ][:limit]


class FailingProvider:
    name = "failing"
    zero_config = True

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        msg = "provider unavailable"
        raise RuntimeError(msg)


def test_normalize_url_strips_tracking_and_trailing_slash() -> None:
    normalized = normalize_url("HTTPS://Example.com/path/?utm_source=x&keep=1")

    assert normalized == "https://example.com/path?keep=1"


def test_rrf_fusion_merges_and_ranks() -> None:
    fused = fuse_results(
        [
            ("provider_a", _results_from_provider_a()),
            ("provider_b", _results_from_provider_b()),
        ],
        limit=5,
    )

    assert len(fused) == 3
    assert fused[0].score >= fused[1].score
    assert all(result.score > 0 for result in fused)


def _results_from_provider_a() -> list[SearchResult]:
    return [
        SearchResult(
            title="Alpha",
            url="https://example.com/a/",
            snippet="first",
            source="provider_a",
        ),
        SearchResult(
            title="Shared",
            url="https://example.com/shared?utm_source=a",
            snippet="shared from a",
            source="provider_a",
        ),
    ]


def _results_from_provider_b() -> list[SearchResult]:
    return [
        SearchResult(
            title="Beta",
            url="https://example.com/b",
            snippet="second",
            source="provider_b",
        ),
        SearchResult(
            title="Shared duplicate",
            url="https://example.com/shared/",
            snippet="shared from b with longer snippet text",
            source="provider_b",
        ),
    ]


def test_rrf_fusion_deduplicates_shared_urls() -> None:
    fused = fuse_results(
        [
            ("provider_a", _results_from_provider_a()),
            ("provider_b", _results_from_provider_b()),
        ],
        limit=10,
    )

    normalized_urls = {normalize_url(result.url) for result in fused}
    assert len(normalized_urls) == len(fused)
    assert len(fused) == 3

    shared = next(result for result in fused if "shared" in result.url)
    assert "shared from b" in shared.snippet
    assert "+" in shared.source


@pytest.mark.asyncio
async def test_federated_search_merges_providers() -> None:
    results = await federated_search([ProviderA(), ProviderB()], "test", limit=3)

    assert len(results) == 3
    assert all(result.score > 0 for result in results)


@pytest.mark.asyncio
async def test_federated_search_graceful_degradation() -> None:
    results = await federated_search(
        [FailingProvider(), ProviderA()],
        "test",
        limit=2,
    )

    assert len(results) == 2
    assert results[0].title == "Alpha"
