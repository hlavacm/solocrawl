"""Tests for httpx-based fetching."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from solocrawl.config import ConcurrencyConfig, Config, FetchConfig, load_config
from solocrawl.core.fetch.client import get_client_for_testing, set_client_for_testing
from solocrawl.core.fetch.fetcher import fetch
from solocrawl.core.models import FetchResult


def _html_response(
    html: str,
    *,
    status: int = 200,
    content_type: str = "text/html; charset=utf-8",
    url: str = "https://example.com/",
) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"Content-Type": content_type},
        text=html,
        request=httpx.Request("GET", url),
    )


async def test_fetch_returns_markdown_for_html(article_html: str) -> None:
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(str(request.url))
        return _html_response(article_html, url=str(request.url))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    result = await fetch("https://example.com/page")

    assert isinstance(result, FetchResult)
    assert result.status == 200
    assert "Understanding Async HTTP Clients" in result.content
    assert result.content_type == "text/html"
    assert result.browser_used is False
    # robots.txt is consulted first (and allows), then the page itself is fetched.
    assert attempts == ["https://example.com/robots.txt", "https://example.com/page"]
    await client.aclose()


async def test_shared_client_is_reused(article_html: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _html_response(article_html, url=str(request.url))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    await fetch("https://example.com/one")
    first_client = get_client_for_testing()
    await fetch("https://example.com/two")
    second_client = get_client_for_testing()

    assert first_client is second_client
    await client.aclose()


async def test_fetch_follows_redirects(article_html: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/redirect":
            return httpx.Response(
                302,
                headers={"Location": "https://example.com/final"},
                request=request,
            )
        return _html_response(article_html, url="https://example.com/final")

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    )
    await set_client_for_testing(client)

    result = await fetch("https://example.com/redirect")

    assert result.url == "https://example.com/final"
    await client.aclose()


async def test_fetch_handles_json_content() -> None:
    payload = '{"hello": "world", "count": 2}'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            text=payload,
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    result = await fetch("https://example.com/data.json")

    assert result.content_type == "application/json"
    assert '"hello": "world"' in result.content
    await client.aclose()


async def test_fetch_handles_pdf_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.4 fake",
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    result = await fetch("https://example.com/file.pdf")

    assert result.content_type == "application/pdf"
    assert "PDF content" in result.content
    await client.aclose()


async def test_fetch_retries_rate_limited_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("solocrawl.core.fetch.fetcher.asyncio.sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                request=request,
            )
        return httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            text="done",
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    config = load_config(env={"SOLOCRAWL_MAX_RETRIES": "2", "SOLOCRAWL_RESPECT_ROBOTS": "false"})
    result = await fetch("https://example.com/rate-limited", config=config)

    assert calls == 2
    assert sleeps == [2.0]
    assert result.content == "done"
    await client.aclose()


async def test_fetch_caps_oversized_response_body() -> None:
    big_body = "A" * 100_000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/plain"},
            text=big_body,
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    config = Config(fetch=FetchConfig(max_response_bytes=1_000))
    result = await fetch("https://example.com/huge", config=config)

    assert len(result.content) <= 1_000
    await client.aclose()


async def test_fetch_force_browser_returns_unavailable_message() -> None:
    config = Config(fetch=FetchConfig(respect_robots=False))
    result = await fetch("https://example.com/js-page", force_browser=True, config=config)

    assert result.status == 0
    assert "not available" in result.content.lower()
    assert result.browser_used is False


async def test_concurrency_is_bounded(article_html: str) -> None:
    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        async with lock:
            active -= 1
        return _html_response(article_html, url=str(request.url))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    config = Config(
        concurrency=ConcurrencyConfig(
            max_concurrent_fetches=2,
            per_domain_limit=2,
            timeout_seconds=5.0,
            max_retries=0,
        ),
        fetch=FetchConfig(respect_robots=False),
    )

    await asyncio.gather(
        fetch("https://example.com/a", config=config),
        fetch("https://example.com/b", config=config),
        fetch("https://example.com/c", config=config),
        fetch("https://example.com/d", config=config),
    )

    assert max_active <= 2
    await client.aclose()
