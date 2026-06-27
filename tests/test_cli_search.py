"""Tests for the CLI search subcommand."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from solocrawl.cli import main
from solocrawl.core.models import SearchResult


def _sample_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Alpha",
            url="https://example.com/a",
            snippet="first hit",
            source="wikipedia",
            score=0.032,
        ),
        SearchResult(
            title="Beta",
            url="https://example.com/b",
            snippet="second hit",
            source="duckduckgo",
            score=0.016,
        ),
    ]


class DummyProvider:
    name = "dummy"
    zero_config = True

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return _sample_results()[:limit]


def test_search_prints_results(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("solocrawl.cli.search.select_providers", return_value=[DummyProvider()]),
        patch(
            "solocrawl.cli.search.federated_search",
            new=AsyncMock(return_value=_sample_results()),
        ),
        patch("solocrawl.cli.search.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(["search", "python asyncio", "--limit", "2"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Alpha" in captured.out
    assert "https://example.com/a" in captured.out
    assert "wikipedia" in captured.out


def test_search_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("solocrawl.cli.search.select_providers", return_value=[DummyProvider()]),
        patch(
            "solocrawl.cli.search.federated_search",
            new=AsyncMock(return_value=_sample_results()),
        ),
        patch("solocrawl.cli.search.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(["search", "python", "--json"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert len(payload) == 2
    assert payload[0]["title"] == "Alpha"


def test_search_graceful_when_one_provider_fails(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("solocrawl.cli.search.select_providers", return_value=[DummyProvider()]),
        patch(
            "solocrawl.cli.search.federated_search",
            new=AsyncMock(return_value=[_sample_results()[0]]),
        ),
        patch("solocrawl.cli.search.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(["search", "python", "--limit", "1"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Alpha" in captured.out


def test_search_rejects_empty_query(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main.main(["search", "   "])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "empty" in captured.err.lower()


def test_search_rejects_unknown_sources(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("solocrawl.cli.search.select_providers", return_value=[]),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(["search", "python", "--sources", "missing"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "no matching providers" in captured.err
