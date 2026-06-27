"""Tests for Playwright browser fallback."""

from __future__ import annotations

import ipaddress
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.browser import (
    RenderedPage,
    close_browser,
    fetch_rendered_html,
    playwright_available,
    reset_browser_state_for_testing,
)
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.fetch.fetcher import fetch


@pytest.fixture(autouse=True)
async def reset_browser() -> AsyncGenerator[None]:
    await reset_browser_state_for_testing()
    yield
    await reset_browser_state_for_testing()


def test_playwright_available_without_install(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert playwright_available() is False


async def test_fetch_uses_browser_when_content_is_empty(article_html: str) -> None:
    empty_html = "<html><body><div></div></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text=empty_html,
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    with patch(
        "solocrawl.core.fetch.fetcher.fetch_rendered_html",
        new=AsyncMock(
            return_value=RenderedPage(
                html=article_html,
                url="https://example.com/js-page",
            )
        ),
    ) as browser_fetch:
        result = await fetch("https://example.com/js-page")

    assert result.browser_used is True
    assert "Understanding Async HTTP Clients" in result.content
    browser_fetch.assert_awaited_once()
    await client.aclose()


async def test_fetch_does_not_use_browser_for_rich_html(article_html: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text=article_html,
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    with patch(
        "solocrawl.core.fetch.fetcher.fetch_rendered_html",
        new=AsyncMock(return_value=article_html),
    ) as browser_fetch:
        result = await fetch("https://example.com/static")

    assert result.browser_used is False
    browser_fetch.assert_not_called()
    await client.aclose()


async def test_fetch_rendered_html_returns_none_without_playwright(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "solocrawl.core.fetch.browser.playwright_available",
        lambda: False,
    )
    config = Config()
    html = await fetch_rendered_html(
        "https://example.com",
        concurrency=config.concurrency,
        browser_config=config.browser,
    )
    assert html is None


async def test_fetch_rendered_html_rejects_internal_final_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePage:
        url = "https://internal.example/secret"

        async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
            return None

        async def content(self) -> str:
            return "<html><body>secret</body></html>"

    class FakeContext:
        async def new_page(self) -> FakePage:
            return FakePage()

    @asynccontextmanager
    async def fake_browser_context(*, proxy=None):
        yield FakeContext()

    async def resolve(host: str, port: int | None):
        if host == "internal.example":
            return (ipaddress.ip_address("127.0.0.1"),)
        return (ipaddress.ip_address("8.8.8.8"),)

    monkeypatch.setattr("solocrawl.core.fetch.browser.playwright_available", lambda: True)
    monkeypatch.setattr("solocrawl.core.fetch.browser._browser_context", fake_browser_context)
    monkeypatch.setattr(
        "solocrawl.core.fetch.url_validation._resolve_host_addresses",
        resolve,
    )

    config = Config()
    rendered = await fetch_rendered_html(
        "https://example.com/page",
        concurrency=config.concurrency,
        browser_config=config.browser,
    )

    assert rendered is None


async def test_close_browser_is_safe_when_not_started() -> None:
    await close_browser()
