"""Tests for the in-memory fetch TTL cache."""

from __future__ import annotations

import httpx
import pytest

from solocrawl.config import Config, FetchConfig
from solocrawl.core.fetch.cache import cache_get, cache_set
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.fetch.fetcher import fetch
from solocrawl.core.models import FetchResult

_PAGE = "<html><body><p>" + ("word " * 60) + "</p></body></html>"


def _result(url: str = "https://example.com/p") -> FetchResult:
    return FetchResult(url=url, content="body", content_type="text/html", status=200)


def test_cache_set_get_roundtrip() -> None:
    result = _result()
    cache_set(result.url, result, 60)
    assert cache_get(result.url) is result


def test_cache_zero_ttl_stores_nothing() -> None:
    result = _result()
    cache_set(result.url, result, 0)
    assert cache_get(result.url) is None


def test_cache_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"t": 1000.0}
    monkeypatch.setattr("solocrawl.core.fetch.cache.time.monotonic", lambda: clock["t"])

    result = _result()
    cache_set(result.url, result, 30)  # expires at t=1030

    clock["t"] = 1020.0
    assert cache_get(result.url) is result

    clock["t"] = 1031.0
    assert cache_get(result.url) is None


def test_cache_evicts_oldest_when_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("solocrawl.core.fetch.cache._MAX_ENTRIES", 3)
    for i in range(3):
        cache_set(f"https://example.com/{i}", _result(f"https://example.com/{i}"), 60)
    cache_set("https://example.com/3", _result("https://example.com/3"), 60)  # overflows

    assert cache_get("https://example.com/0") is None  # oldest evicted
    assert cache_get("https://example.com/3") is not None  # new entry stored
    assert cache_get("https://example.com/1") is not None  # rest retained


def _page_counting_client() -> tuple[httpx.AsyncClient, list[str]]:
    page_hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/robots.txt":
            page_hits.append(str(request.url))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text=_PAGE,
            request=request,
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), page_hits


async def test_fetch_serves_second_call_from_cache() -> None:
    client, page_hits = _page_counting_client()
    await set_client_for_testing(client)

    config = Config(fetch=FetchConfig(cache_ttl_seconds=60))
    await fetch("https://example.com/page", config=config)
    await fetch("https://example.com/page", config=config)

    assert len(page_hits) == 1
    await client.aclose()


async def test_fetch_without_cache_refetches() -> None:
    client, page_hits = _page_counting_client()
    await set_client_for_testing(client)

    config = Config(fetch=FetchConfig(cache_ttl_seconds=0))
    await fetch("https://example.com/page", config=config)
    await fetch("https://example.com/page", config=config)

    assert len(page_hits) == 2
    await client.aclose()
