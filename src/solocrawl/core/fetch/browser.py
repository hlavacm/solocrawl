"""Playwright browser pool for JS-heavy page fallback."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from solocrawl.config import BrowserConfig, ConcurrencyConfig, ProxyConfig
from solocrawl.core.fetch.url_validation import ensure_fetch_url_resolves_allowed
from solocrawl.core.proxy import get_proxy_pool

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright  # pyright: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

_playwright: Playwright | None = None
_browser: Browser | None = None
_browser_lock = asyncio.Lock()
_browser_semaphore: asyncio.Semaphore | None = None
_browser_semaphore_limit: int | None = None


@dataclass(frozen=True)
class RenderedPage:
    """HTML rendered by Playwright and the final browser URL."""

    html: str
    url: str


def playwright_available() -> bool:
    """Return True when Playwright is installed."""
    import importlib.util

    return importlib.util.find_spec("playwright") is not None


async def fetch_rendered_html(
    url: str,
    *,
    concurrency: ConcurrencyConfig,
    browser_config: BrowserConfig,
    proxy_config: ProxyConfig | None = None,
    allow_internal_urls: bool = False,
) -> RenderedPage | None:
    """Render a page with Playwright and return its HTML, or None if unavailable."""
    if not browser_config.allowed or not playwright_available():
        return None

    if proxy_config is not None and proxy_config.enabled:
        pool = get_proxy_pool(proxy_config)
    else:
        pool = None
    endpoint = (
        pool.select(domain=urlparse(url).netloc) if pool is not None and pool.enabled else None
    )
    playwright_proxy = endpoint.playwright_proxy() if endpoint is not None else None

    semaphore = _get_browser_semaphore(concurrency)
    async with semaphore:
        try:
            await ensure_fetch_url_resolves_allowed(
                url,
                allow_internal=allow_internal_urls,
            )
            async with _browser_context(proxy=playwright_proxy) as context:
                page = await context.new_page()
                timeout_ms = int(concurrency.timeout_seconds * 1000)
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                await ensure_fetch_url_resolves_allowed(
                    page.url,
                    allow_internal=allow_internal_urls,
                )
                return RenderedPage(html=await page.content(), url=page.url)
        except Exception as exc:
            logger.warning("playwright fetch failed for %s: %s", url, exc)
            return None


def _get_browser_semaphore(concurrency: ConcurrencyConfig) -> asyncio.Semaphore:
    global _browser_semaphore, _browser_semaphore_limit
    limit = max(1, min(concurrency.max_concurrent_fetches, concurrency.per_domain_limit))
    if _browser_semaphore is None or _browser_semaphore_limit != limit:
        _browser_semaphore = asyncio.Semaphore(limit)
        _browser_semaphore_limit = limit
    return _browser_semaphore


@asynccontextmanager
async def _browser_context(*, proxy: dict[str, str] | None = None):
    browser = await _get_browser()
    context = await browser.new_context(proxy=proxy)
    try:
        yield context
    finally:
        await context.close()


async def _get_browser() -> Browser:
    global _playwright, _browser
    async with _browser_lock:
        if _browser is not None and _browser.is_connected():
            return _browser

        import importlib

        async_playwright_module = importlib.import_module("playwright.async_api")
        async_playwright = async_playwright_module.async_playwright

        if _playwright is None:
            _playwright = await async_playwright().start()
        assert _playwright is not None
        _browser = await _playwright.chromium.launch(headless=True)
        return _browser


async def close_browser() -> None:
    """Close the shared Playwright browser and stop Playwright."""
    global _playwright, _browser, _browser_semaphore, _browser_semaphore_limit
    async with _browser_lock:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _playwright is not None:
            await _playwright.stop()
            _playwright = None
        _browser_semaphore = None
        _browser_semaphore_limit = None


async def reset_browser_state_for_testing() -> None:
    """Reset browser singleton state (tests only)."""
    await close_browser()
