"""Browser interception must stop forbidden requests before network I/O."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from solocrawl.config import BrowserConfig, ConcurrencyConfig, FetchConfig
from solocrawl.core.fetch import browser
from solocrawl.core.fetch.url_validation import FetchUrlError


class Request:
    def __init__(self, url: str, frame: object, *, navigation: bool = True) -> None:
        self.url = url
        self.frame = frame
        self.method = "GET"
        self.navigation = navigation

    def is_navigation_request(self) -> bool:
        return self.navigation


class Route:
    def __init__(self, status: int = 200, location: str = "") -> None:
        self.fetch = AsyncMock(
            return_value=type(
                "Response",
                (),
                {
                    "dispose": AsyncMock(),
                    "status": status,
                    "headers": {"location": location} if location else {},
                },
            )()
        )
        self.abort = AsyncMock()
        self.fulfill = AsyncMock()


class Context:
    def __init__(self, *, redirect: str = "", subresource: str = "") -> None:
        self.main_frame = object()
        self.url = "about:blank"
        self.redirect = redirect
        self.subresource = subresource
        self.navigation_aborted = False
        self.routes: list[Route] = []

    async def route_web_socket(self, pattern: str, handler) -> None:
        self.websocket_handler = handler

    async def route(self, pattern: str, handler) -> None:
        assert pattern == "**/*"
        self.handler = handler

    async def new_page(self):
        return self

    async def close(self) -> None:
        self.navigation_aborted = False

    async def goto(self, url: str, **kwargs) -> None:
        if self.navigation_aborted:
            raise RuntimeError("navigation interrupted by chrome-error://chromewebdata/")
        self.url = url
        route = Route(302 if self.redirect else 200, self.redirect)
        self.redirect = ""
        self.routes.append(route)
        await self.handler(route, Request(url, self.main_frame))
        if route.abort.await_count:
            # An aborted main navigation can still commit Chromium's error document.
            self.navigation_aborted = True
            raise RuntimeError("navigation aborted")
        if self.subresource:
            resource = Route()
            self.routes.append(resource)
            await self.handler(resource, Request(self.subresource, object(), navigation=False))

    async def content(self) -> str:
        return "<html><body>safe</body></html>"


async def render(monkeypatch: pytest.MonkeyPatch, context: Context):
    @asynccontextmanager
    async def fake_context(**kwargs):
        yield context

    async def check(url: str, **kwargs) -> None:
        if "127.0.0.1" in url:
            raise FetchUrlError("internal address forbidden")

    monkeypatch.setattr(browser, "playwright_available", lambda: True)
    monkeypatch.setattr(browser, "_browser_context", fake_context)
    monkeypatch.setattr(browser, "ensure_fetch_url_resolves_allowed", check)
    return await browser.fetch_rendered_html(
        "https://example.com/start",
        concurrency=ConcurrencyConfig(),
        browser_config=BrowserConfig(),
        fetch_config=FetchConfig(respect_robots=False),
    )


async def test_browser_rejects_redirect_before_target_request(monkeypatch: pytest.MonkeyPatch):
    context = Context(redirect="http://127.0.0.1/secret")
    with pytest.raises(FetchUrlError):
        await render(monkeypatch, context)
    assert len(context.routes) == 1
    context.routes[0].fetch.assert_awaited_once_with(max_redirects=0, timeout=30000)


async def test_browser_aborts_forbidden_subresource(monkeypatch: pytest.MonkeyPatch):
    context = Context(subresource="http://127.0.0.1/secret")
    result = await render(monkeypatch, context)
    assert result is not None
    context.routes[1].fetch.assert_not_called()
    context.routes[1].abort.assert_awaited_once()


async def test_browser_allowed_redirect_preserves_final_url(monkeypatch: pytest.MonkeyPatch):
    context = Context(redirect="https://other.example/final")
    result = await render(monkeypatch, context)
    assert result is not None
    assert result.url == "https://other.example/final"
    assert len(context.routes) == 2


async def test_browser_blocks_websocket_route(monkeypatch: pytest.MonkeyPatch) -> None:
    context = Context()
    await render(monkeypatch, context)
    assert hasattr(context, "websocket_handler")
    websocket = SimpleNamespace(close=AsyncMock())
    await context.websocket_handler(websocket)
    websocket.close.assert_awaited_once()


@pytest.mark.parametrize("navigation", [True, False], ids=["iframe", "xhr"])
async def test_redirected_subrequests_are_aborted_without_replaying_credentials(
    monkeypatch: pytest.MonkeyPatch,
    navigation: bool,
) -> None:
    context = Context(subresource="https://example.com/resource")
    original_goto = context.goto

    async def goto(url: str, **kwargs) -> None:
        resource = context.subresource
        context.subresource = ""
        await original_goto(url, **kwargs)
        route = Route(302, "https://different.example/final")
        context.routes.append(route)
        await context.handler(route, Request(resource, object(), navigation=navigation))

    context.goto = goto
    result = await render(monkeypatch, context)
    assert result is not None
    resource = context.routes[-1]
    assert resource.fetch.await_count == 1
    resource.fulfill.assert_not_awaited()
    resource.abort.assert_awaited_once()
