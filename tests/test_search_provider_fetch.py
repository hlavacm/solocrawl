"""Provider-level (network path) tests for search providers via MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.search.providers.arxiv import ArxivProvider
from solocrawl.core.search.providers.duckduckgo import DuckDuckGoProvider
from solocrawl.core.search.providers.github import GitHubProvider
from solocrawl.core.search.providers.hackernews import HackerNewsProvider
from solocrawl.core.search.providers.mdn import MdnProvider
from solocrawl.core.search.providers.pubmed import PubMedProvider
from solocrawl.core.search.providers.searxng import SearxngProvider
from solocrawl.core.search.providers.stackexchange import StackExchangeProvider
from solocrawl.core.search.providers.wikidata import WikidataProvider
from solocrawl.core.search.providers.wikipedia import WikipediaProvider

_ALL = [
    ArxivProvider,
    GitHubProvider,
    HackerNewsProvider,
    MdnProvider,
    PubMedProvider,
    SearxngProvider,
    StackExchangeProvider,
    WikidataProvider,
    WikipediaProvider,
]

# Providers that go through httpx and catch HTTPError -> [] (excludes ddgs-based and env-gated).
_HTTPX = [
    ArxivProvider,
    GitHubProvider,
    HackerNewsProvider,
    MdnProvider,
    PubMedProvider,
    StackExchangeProvider,
    WikidataProvider,
    WikipediaProvider,
]


@pytest.mark.parametrize("provider_cls", _ALL)
async def test_search_empty_query_returns_empty(provider_cls) -> None:
    assert await provider_cls(config=Config()).search("   ") == []


async def test_duckduckgo_empty_query_returns_empty() -> None:
    assert await DuckDuckGoProvider().search("   ") == []


@pytest.mark.parametrize("provider_cls", _HTTPX)
async def test_search_http_error_degrades_to_empty(provider_cls) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    try:
        assert await provider_cls(config=Config()).search("anything", limit=3) == []
    finally:
        await client.aclose()


async def test_arxiv_search_happy(read_fixture) -> None:
    body = read_fixture("arxiv_search.xml")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    results = await ArxivProvider(config=Config()).search("attention", limit=5)
    assert len(results) == 2
    await client.aclose()


async def test_arxiv_timeout_diagnostic_identifies_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await set_client_for_testing(client)
        assert await ArxivProvider(config=Config()).search("python", limit=3) == []
    assert "ReadTimeout" in caplog.text


async def test_hackernews_search_happy(read_fixture) -> None:
    payload = json.loads(read_fixture("hackernews_search.json"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    results = await HackerNewsProvider(config=Config()).search("python", limit=5)
    assert len(results) == 2
    await client.aclose()


async def test_mdn_search_happy() -> None:
    payload = {
        "documents": [
            {
                "title": "Fetch API",
                "mdn_url": "/en-US/docs/Web/API/Fetch_API",
                "summary": "Fetch resources.",
                "score": 1.0,
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    results = await MdnProvider(config=Config()).search("fetch", limit=5)
    assert results[0].url.endswith("/Web/API/Fetch_API")
    await client.aclose()


async def test_searxng_search_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOLOCRAWL_SEARXNG_URL", "https://searx.example/")
    payload = {"results": [{"title": "R", "url": "https://e.example", "content": "c"}]}
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json=payload, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    results = await SearxngProvider(config=Config()).search("rust", limit=5)
    assert results[0].title == "R"
    assert "searx.example/search" in requests[0]
    await client.aclose()


async def test_searxng_http_error_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOLOCRAWL_SEARXNG_URL", "https://searx.example")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    assert await SearxngProvider(config=Config()).search("rust") == []
    await client.aclose()
