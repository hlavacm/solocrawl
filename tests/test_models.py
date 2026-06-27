"""Tests for shared core data types."""

from solocrawl.core.models import FetchResult, PackageInfo, SearchResult


def test_search_result_defaults() -> None:
    result = SearchResult(
        title="Example",
        url="https://example.com",
        snippet="An example page.",
        source="wikipedia",
    )
    assert result.score == 0.0
    assert result.raw is None


def test_fetch_result_fields() -> None:
    result = FetchResult(
        url="https://example.com/final",
        content="# Title",
        content_type="text/markdown",
        status=200,
        browser_used=True,
    )
    assert result.browser_used is True


def test_package_info_optional_urls() -> None:
    info = PackageInfo(
        name="requests",
        ecosystem="pypi",
        latest="2.32.0",
        versions=["2.32.0", "2.31.0"],
    )
    assert info.repository is None
    assert info.homepage is None
    assert info.changelog is None
