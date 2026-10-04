"""Playwright browser pool for JS-heavy page fallback."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from urllib.parse import urljoin, urlparse

import httpx

from solocrawl.config import BrowserConfig, ConcurrencyConfig, FetchConfig, ProxyConfig
from solocrawl.core.fetch.client import get_client, resolve_user_agent
from solocrawl.core.fetch.robots import RobotsDisallowedError, is_fetch_allowed
from solocrawl.core.fetch.url_validation import FetchUrlError, ensure_fetch_url_resolves_allowed
from solocrawl.core.proxy import get_proxy_pool

if TYPE_CHECKING:
    from playwright.async_api import (  # pyright: ignore[reportMissingImports]
        Browser,
        BrowserContext,
        Playwright,
        ProxySettings,
        Request,
        Route,
        WebSocketRoute,
    )

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
    fetch_config: FetchConfig | None = None,
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

    policy = fetch_config or FetchConfig()
    semaphore = _get_browser_semaphore(concurrency)
    async with semaphore:
        try:
            await ensure_fetch_url_resolves_allowed(url, allow_internal=allow_internal_urls)
            async with AsyncExitStack() as stack:
                if endpoint is not None:
                    robots_client = await stack.enter_async_context(
                        httpx.AsyncClient(
                            proxy=endpoint.httpx_proxy_url(),
                            timeout=concurrency.timeout_seconds,
                            trust_env=False,
                            headers={"User-Agent": resolve_user_agent(policy.user_agent)},
                        )
                    )
                else:
                    robots_client = await get_client(concurrency, user_agent=policy.user_agent)
                context = await stack.enter_async_context(
                    _browser_context(
                        proxy=playwright_proxy, user_agent=resolve_user_agent(policy.user_agent)
                    )
                )
                return await _render_guarded(
                    context,
                    url,
                    concurrency=concurrency,
                    policy=policy,
                    allow_internal=allow_internal_urls,
                    robots_client=robots_client,
                )
        except FetchUrlError, RobotsDisallowedError:
            raise
        except Exception:
            # Exception text may contain proxy credentials; log only the requested page.
            logger.warning("playwright fetch failed for %s", url)
            return None


async def _render_guarded(
    context: BrowserContext,
    url: str,
    *,
    concurrency: ConcurrencyConfig,
    policy: FetchConfig,
    allow_internal: bool,
    robots_client: httpx.AsyncClient,
) -> RenderedPage:
    page = await context.new_page()
    timeout_ms = int(concurrency.timeout_seconds * 1000)
    redirect_target: str | None = None
    navigation_error: Exception | None = None

    async def check(target: str) -> None:
        await ensure_fetch_url_resolves_allowed(target, allow_internal=allow_internal)
        if policy.respect_robots and not await is_fetch_allowed(
            target,
            user_agent=resolve_user_agent(policy.user_agent),
            client=robots_client,
        ):
            raise RobotsDisallowedError(f"robots.txt disallows fetching {target}")

    async def intercept(route: Route, request: Request) -> None:
        nonlocal redirect_target, navigation_error
        main_navigation = request.is_navigation_request() and request.frame == page.main_frame
        target = request.url
        try:
            await check(target)
            # Fetch one hop only: Chromium must never follow an unchecked redirect.
            response = await route.fetch(max_redirects=0, timeout=timeout_ms)
            if response.status in {301, 302, 303, 307, 308} and "location" in response.headers:
                next_url = urljoin(target, response.headers["location"])
                await check(next_url)
                await response.dispose()
                if main_navigation:
                    redirect_target = next_url
                # A subrequest cannot be replayed/fulfilled at another URL without changing
                # auth, body, relative URLs and browser origin semantics. Fail closed instead.
                await route.abort()
                return
            await route.fulfill(response=response)
        except Exception as exc:
            if main_navigation:
                navigation_error = exc
            await route.abort()

    async def block_websocket(route: WebSocketRoute) -> None:
        # WebSocket connections bypass ordinary HTTP routing and are unnecessary for extraction.
        await route.close()

    await context.route_web_socket("**/*", block_websocket)
    await context.route("**/*", intercept)
    target = url
    for _ in range(21):
        redirect_target = None
        navigation_error = None
        await check(target)
        try:
            await page.goto(target, wait_until="networkidle", timeout=timeout_ms)
        except Exception:
            if navigation_error is not None:
                raise navigation_error from None
            if redirect_target is None:
                raise
        if navigation_error is not None:
            raise navigation_error
        if redirect_target is not None:
            target = redirect_target
            # Aborting the old navigation can asynchronously commit Chromium's error page.
            # Close it before navigating again, retaining cookies in the same context.
            await page.close()
            page = await context.new_page()
            continue
        await check(page.url)
        return RenderedPage(html=await page.content(), url=page.url)
    raise FetchUrlError("too many browser redirects")


def _get_browser_semaphore(concurrency: ConcurrencyConfig) -> asyncio.Semaphore:
    global _browser_semaphore, _browser_semaphore_limit
    limit = max(1, min(concurrency.max_concurrent_fetches, concurrency.per_domain_limit))
    if _browser_semaphore is None or _browser_semaphore_limit != limit:
        _browser_semaphore = asyncio.Semaphore(limit)
        _browser_semaphore_limit = limit
    return _browser_semaphore


@asynccontextmanager
async def _browser_context(*, proxy: dict[str, str] | None = None, user_agent: str | None = None):
    browser = await _get_browser()
    context = await browser.new_context(
        proxy=cast("ProxySettings | None", proxy), service_workers="block", user_agent=user_agent
    )
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
