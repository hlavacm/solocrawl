"""Tests for the StackExchange search provider."""

from __future__ import annotations

import json
from collections.abc import Generator

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.search import clear_registry, select_providers
from solocrawl.core.search import registry as search_registry
from solocrawl.core.search.providers import stackexchange as stackexchange_module
from solocrawl.core.search.providers.stackexchange import (
    StackExchangeProvider,
    _parse_search_response,
)


@pytest.fixture(autouse=True)
def stackexchange_registered() -> Generator[None]:
    saved = dict(search_registry._REGISTRY)
    clear_registry()
    stackexchange_module.register("stackexchange", zero_config=True, configurable=True)(
        StackExchangeProvider
    )
    yield
    clear_registry()
    search_registry._REGISTRY.update(saved)


def test_parse_search_response_maps_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("stackexchange_search.json"))
    results = _parse_search_response(payload, limit=5)

    assert len(results) == 2
    assert results[0].title.startswith("How do I use asyncio.gather")
    assert "stackoverflow.com" in results[0].url
    assert "asyncio.gather" in results[0].snippet
    assert results[0].source == "stackexchange"
    assert results[0].score == 128.0


def test_parse_search_response_empty_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("stackexchange_search_empty.json"))
    results = _parse_search_response(payload, limit=5)

    assert results == []


async def test_stackexchange_search_uses_shared_client(read_fixture) -> None:
    fixture_body = read_fixture("stackexchange_search.json")
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

    provider = StackExchangeProvider(config=Config())
    results = await provider.search("asyncio gather", limit=2)

    assert len(results) == 2
    assert requests
    assert "api.stackexchange.com/2.3/search/advanced" in requests[0]
    assert "filter=withbody" in requests[0]
    await client.aclose()


async def test_stackexchange_search_http_error_returns_empty_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = StackExchangeProvider(config=Config())
    results = await provider.search("asyncio", limit=3)

    assert results == []
    await client.aclose()


def test_stackexchange_is_zero_config_in_selector() -> None:
    providers = select_providers(Config(), env={})
    names = {provider.name for provider in providers}

    assert "stackexchange" in names
