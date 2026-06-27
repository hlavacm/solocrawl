"""Coverage of the Playwright render path using an injected fake playwright."""

from __future__ import annotations

import sys
import types

import pytest

from solocrawl.config import BrowserConfig, ConcurrencyConfig
from solocrawl.core.fetch import browser as browser_mod


class _Page:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.url = "about:blank"

    async def goto(self, url: str, **_kw: object) -> None:
        if self._fail:
            raise RuntimeError("navigation failed")
        self.url = url

    async def content(self) -> str:
        return "<html><body>rendered ok</body></html>"


class _Context:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    async def new_page(self) -> _Page:
        return _Page(self._fail)

    async def close(self) -> None:
        pass


class _Browser:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self._connected = True

    def is_connected(self) -> bool:
        return self._connected

    async def new_context(self, proxy: object = None) -> _Context:
        return _Context(self._fail)

    async def close(self) -> None:
        self._connected = False


class _Chromium:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    async def launch(self, headless: bool = True) -> _Browser:
        return _Browser(self._fail)


class _Playwright:
    def __init__(self, fail: bool = False) -> None:
        self.chromium = _Chromium(fail)

    async def stop(self) -> None:
        pass


class _Starter:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    async def start(self) -> _Playwright:
        return _Playwright(self._fail)


def _install_fake(monkeypatch: pytest.MonkeyPatch, *, fail: bool = False) -> None:
    monkeypatch.setattr(browser_mod, "playwright_available", lambda: True)
    module = types.ModuleType("playwright.async_api")
    module.async_playwright = lambda: _Starter(fail)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", module)


async def test_render_success_and_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake(monkeypatch)
    kwargs = {"concurrency": ConcurrencyConfig(), "browser_config": BrowserConfig(allowed=True)}

    rendered = await browser_mod.fetch_rendered_html("https://example.com", **kwargs)
    assert rendered is not None
    assert "rendered ok" in rendered.html
    assert rendered.url == "https://example.com"

    # Second call should reuse the still-connected browser.
    rendered2 = await browser_mod.fetch_rendered_html("https://example.com/2", **kwargs)
    assert rendered2 is not None
    assert "rendered ok" in rendered2.html
    assert rendered2.url == "https://example.com/2"

    await browser_mod.close_browser()


async def test_render_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake(monkeypatch, fail=True)
    html = await browser_mod.fetch_rendered_html(
        "https://example.com",
        concurrency=ConcurrencyConfig(),
        browser_config=BrowserConfig(allowed=True),
    )
    assert html is None
    await browser_mod.close_browser()


async def test_render_disabled_returns_none() -> None:
    html = await browser_mod.fetch_rendered_html(
        "https://example.com",
        concurrency=ConcurrencyConfig(),
        browser_config=BrowserConfig(allowed=False),
    )
    assert html is None
