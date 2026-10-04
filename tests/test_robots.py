"""Tests for robots.txt enforcement in the fetch path."""

from __future__ import annotations

from urllib.robotparser import RobotFileParser

import httpx
import pytest

from solocrawl.config import Config, FetchConfig
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.fetch.fetcher import RobotsDisallowedError, fetch

_PAGE_HTML = "<html><body><h1>Hello</h1><p>" + ("word " * 50) + "</p></body></html>"
_ROBOTS = "User-agent: *\nDisallow: /private\n"


def _handler_factory(requests: list[str], *, robots_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(robots_status, text=_ROBOTS, request=request)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text=_PAGE_HTML,
            request=request,
        )

    return handler


async def test_robots_disallow_blocks_fetch() -> None:
    requests: list[str] = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler_factory(requests)))
    await set_client_for_testing(client)

    with pytest.raises(RobotsDisallowedError):
        await fetch("https://example.com/private/page", config=Config())

    # The page itself was never requested, only robots.txt.
    assert requests == ["https://example.com/robots.txt"]
    await client.aclose()


async def test_robots_allow_lets_fetch_through() -> None:
    requests: list[str] = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler_factory(requests)))
    await set_client_for_testing(client)

    result = await fetch("https://example.com/public/page", config=Config())

    assert "word" in result.content
    assert result.status == 200
    assert "https://example.com/public/page" in requests
    await client.aclose()


async def test_robots_missing_is_fail_open() -> None:
    requests: list[str] = []
    handler = _handler_factory(requests, robots_status=404)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    result = await fetch("https://example.com/private/page", config=Config())

    assert "word" in result.content
    assert result.status == 200
    await client.aclose()


async def test_robots_unreachable_is_fail_open() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text=_PAGE_HTML,
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    result = await fetch("https://example.com/private/page", config=Config())

    assert "word" in result.content
    assert result.status == 200
    await client.aclose()


async def test_robots_cache_evicts_oldest_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    from solocrawl.core.fetch import robots as robots_module

    monkeypatch.setattr(robots_module, "_MAX_CACHE_ENTRIES", 2)

    async def fake_load(base: str, *, client: httpx.AsyncClient) -> RobotFileParser:
        parser = RobotFileParser()
        parser.parse([])
        return parser

    monkeypatch.setattr(robots_module, "_load_parser", fake_load)

    client = httpx.AsyncClient(trust_env=False)
    await set_client_for_testing(client)

    await robots_module.is_fetch_allowed("https://a.example/page", user_agent="*", client=client)
    await robots_module.is_fetch_allowed("https://b.example/page", user_agent="*", client=client)
    await robots_module.is_fetch_allowed("https://c.example/page", user_agent="*", client=client)

    assert "https://a.example" not in robots_module._cache
    assert "https://b.example" in robots_module._cache
    assert "https://c.example" in robots_module._cache
    await client.aclose()


async def test_robots_cache_avoids_refetch() -> None:
    requests: list[str] = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler_factory(requests)))
    await set_client_for_testing(client)

    await fetch("https://example.com/one", config=Config())
    await fetch("https://example.com/two", config=Config())

    robots_hits = [url for url in requests if url.endswith("/robots.txt")]
    assert len(robots_hits) == 1
    await client.aclose()


async def test_robots_disabled_skips_check() -> None:
    requests: list[str] = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler_factory(requests)))
    await set_client_for_testing(client)

    config = Config(fetch=FetchConfig(respect_robots=False))
    result = await fetch("https://example.com/private/page", config=config)

    assert "word" in result.content
    assert result.status == 200
    assert all(not url.endswith("/robots.txt") for url in requests)
    await client.aclose()
