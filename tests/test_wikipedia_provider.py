"""Tests for the Wikipedia search provider."""

from __future__ import annotations

import json

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.search import clear_registry, select_providers
from solocrawl.core.search.providers import wikipedia as wikipedia_module
from solocrawl.core.search.providers.wikipedia import WikipediaProvider, _parse_search_response


@pytest.fixture(autouse=True)
def wikipedia_registered() -> None:
    clear_registry()
    wikipedia_module.register("wikipedia", zero_config=True)(WikipediaProvider)


def test_parse_search_response_maps_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("wikipedia_search.json"))
    results = _parse_search_response(payload, wiki="en", limit=5)

    assert len(results) == 2
    assert results[0].title == "Python (programming language)"
    assert results[0].url == "https://en.wikipedia.org/wiki/Python_(programming_language)"
    assert results[0].source == "wikipedia"
    assert "programming" in results[0].snippet.lower()
    assert results[1].title == "Python Software Foundation"


def test_parse_search_response_empty_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("wikipedia_search_empty.json"))
    results = _parse_search_response(payload, wiki="en", limit=5)

    assert results == []


async def test_wikipedia_search_uses_shared_client(read_fixture) -> None:
    fixture_body = read_fixture("wikipedia_search.json")
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(
            200,
            json=json.loads(fixture_body),
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = WikipediaProvider(config=Config())
    results = await provider.search("python", limit=2)

    assert len(results) == 2
    assert requests
    assert "wikipedia.org/w/api.php" in requests[0]
    assert "srsearch=python" in requests[0]
    await client.aclose()


async def test_wikipedia_search_http_error_returns_empty_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = WikipediaProvider(config=Config())
    results = await provider.search("python", limit=3)

    assert results == []
    await client.aclose()


async def test_wikipedia_search_empty_query_returns_empty_list() -> None:
    provider = WikipediaProvider(config=Config())
    results = await provider.search("   ", limit=3)

    assert results == []


def test_wikipedia_is_zero_config_in_selector() -> None:
    providers = select_providers(Config(), env={})
    names = {provider.name for provider in providers}

    assert "wikipedia" in names
