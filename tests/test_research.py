"""Tests for the research tool (search + scrape + aggregation)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from solocrawl.cli import main
from solocrawl.core.models import FetchResult, SearchResult
from solocrawl.core.research import ResearchDocument, research, research_to_markdown


def _hits() -> list[SearchResult]:
    return [
        SearchResult(title="A", url="https://a.example", snippet="s", source="wikipedia"),
        SearchResult(title="B", url="https://b.example", snippet="s", source="duckduckgo"),
    ]


async def test_research_aggregates_scraped_content() -> None:
    async def fake_fetch(url: str, *, config: object = None) -> FetchResult:
        return FetchResult(
            url=url, content=f"content of {url}", content_type="text/html", status=200
        )

    with (
        patch("solocrawl.core.research.select_providers", return_value=[object()]),
        patch("solocrawl.core.research.federated_search", new=AsyncMock(return_value=_hits())),
        patch("solocrawl.core.research.fetch", new=AsyncMock(side_effect=fake_fetch)),
    ):
        documents = await research("python", depth=2)

    assert [doc.url for doc in documents] == ["https://a.example", "https://b.example"]
    assert documents[0].content == "content of https://a.example"
    assert documents[0].error is None


async def test_research_records_fetch_errors() -> None:
    async def fake_fetch(url: str, *, config: object = None) -> FetchResult:
        if url == "https://b.example":
            raise RuntimeError("boom")
        return FetchResult(url=url, content="ok", content_type="text/html", status=200)

    with (
        patch("solocrawl.core.research.select_providers", return_value=[object()]),
        patch("solocrawl.core.research.federated_search", new=AsyncMock(return_value=_hits())),
        patch("solocrawl.core.research.fetch", new=AsyncMock(side_effect=fake_fetch)),
    ):
        documents = await research("python", depth=2)

    assert documents[1].content is None
    assert documents[1].error is not None
    assert "boom" in documents[1].error


async def test_research_empty_query_returns_no_documents() -> None:
    assert await research("   ", depth=3) == []


def test_research_to_markdown_includes_sources_and_errors() -> None:
    documents = [
        ResearchDocument(title="A", url="https://a.example", source="wikipedia", content="body A"),
        ResearchDocument(
            title="B", url="https://b.example", source="ddg", content=None, error="boom"
        ),
    ]
    markdown = research_to_markdown("python", documents)

    assert "# Research: python" in markdown
    assert "## 1. A" in markdown
    assert "https://a.example" in markdown
    assert "_[fetch failed: boom]_" in markdown


def test_cli_research_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    documents = [
        ResearchDocument(title="A", url="https://a.example", source="wikipedia", content="body A"),
    ]
    with (
        patch("solocrawl.cli.research.research", new=AsyncMock(return_value=documents)),
        patch("solocrawl.cli.research.close_client", new=AsyncMock(return_value=None)),
        patch("solocrawl.cli.research.close_browser", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(["research", "python", "--depth", "1", "--json"])

    assert exc_info.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["title"] == "A"
    assert payload[0]["url"] == "https://a.example"


def test_cli_research_rejects_excessive_depth(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main.main(["research", "python", "--depth", "999"])

    assert exc_info.value.code == 1
    assert "--depth must be at most" in capsys.readouterr().err
