"""Tests for the DuckDuckGo search provider."""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest

from solocrawl.config import Config
from solocrawl.core.search import clear_registry, select_providers
from solocrawl.core.search import registry as search_registry
from solocrawl.core.search.providers import duckduckgo as duckduckgo_module
from solocrawl.core.search.providers.duckduckgo import (
    DuckDuckGoProvider,
    _map_ddgs_results,
    _run_ddgs_text,
)


@pytest.fixture(autouse=True)
def duckduckgo_registered() -> Generator[None]:
    saved = dict(search_registry._REGISTRY)
    clear_registry()
    duckduckgo_module.register("duckduckgo", zero_config=True, configurable=True)(
        DuckDuckGoProvider
    )
    yield
    clear_registry()
    search_registry._REGISTRY.update(saved)


def test_map_ddgs_results_fixture(read_fixture) -> None:
    raw = json.loads(read_fixture("ddgs_text.json"))
    results = _map_ddgs_results(raw, limit=5)

    assert len(results) == 2
    assert results[0].source == "duckduckgo"
    assert results[0].url.startswith("https://docs.python.org")


@pytest.mark.asyncio
async def test_duckduckgo_search_uses_to_thread(read_fixture, monkeypatch) -> None:
    fixture = json.loads(read_fixture("ddgs_text.json"))

    def fake_run(query: str, *, limit: int, timeout: float) -> list[dict[str, object]]:
        assert query == "python asyncio"
        assert limit == 2
        assert timeout == 30.0
        return fixture

    monkeypatch.setattr(
        "solocrawl.core.search.providers.duckduckgo._run_ddgs_text",
        fake_run,
    )

    provider = DuckDuckGoProvider()
    results = await provider.search("python asyncio", limit=2)

    assert len(results) == 2


@pytest.mark.asyncio
async def test_duckduckgo_search_error_returns_empty_list(monkeypatch) -> None:
    def failing_run(query: str, *, limit: int, timeout: float) -> list[dict[str, object]]:
        msg = "rate limited"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        "solocrawl.core.search.providers.duckduckgo._run_ddgs_text",
        failing_run,
    )

    provider = DuckDuckGoProvider()
    results = await provider.search("python", limit=3)

    assert results == []


def test_duckduckgo_is_zero_config_in_selector() -> None:
    providers = select_providers(Config(), env={})
    names = {provider.name for provider in providers}

    assert "duckduckgo" in names


def test_run_ddgs_text_delegates_to_ddgs(monkeypatch) -> None:
    class FakeDDGS:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 30.0

        def text(self, query: str, **kwargs: object) -> list[dict[str, str]]:
            assert query == "hello"
            assert kwargs["max_results"] == 3
            return [{"title": "Hi", "href": "https://example.com", "body": "snippet"}]

    monkeypatch.setattr(
        "solocrawl.core.search.providers.duckduckgo._import_ddgs",
        lambda: FakeDDGS,
    )

    results = _run_ddgs_text("hello", limit=3)
    assert len(results) == 1
