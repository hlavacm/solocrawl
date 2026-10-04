"""Real Chromium against local fixtures, without public websites or accounts."""

from __future__ import annotations

import asyncio
import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import pytest

from solocrawl.config import BrowserConfig, ConcurrencyConfig, FetchConfig
from solocrawl.core.fetch import browser
from solocrawl.core.fetch.url_validation import FetchUrlError, ensure_fetch_url_resolves_allowed

pytestmark = pytest.mark.browser


@asynccontextmanager
async def fixture_site(
    routes: dict[str, tuple[int, dict[str, str], str]], hits: list[str]
) -> AsyncIterator[str]:
    async def respond(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
            path = request.split(b" ")[1].decode()
            hits.append(path)
            status, headers, body = routes.get(path, (404, {}, "not found"))
            data = body.encode()
            headers = {
                "Content-Type": "text/html",
                "Content-Length": str(len(data)),
                "Connection": "close",
                **headers,
            }
            response = f"HTTP/1.1 {status} Response\r\n" + "".join(
                f"{key}: {value}\r\n" for key, value in headers.items()
            )
            writer.write(response.encode() + b"\r\n" + data)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        yield f"http://127.0.0.1:{port}"


async def test_chromium_blocks_redirect_iframe_script_and_subrequests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden_hits: list[str] = []
    main_hits: list[str] = []
    render_errors: list[str] = []
    original_render = browser._render_guarded

    async def diagnostic_render(*args, **kwargs):
        try:
            return await original_render(*args, **kwargs)
        except Exception:
            render_errors.append(traceback.format_exc())
            raise

    monkeypatch.setattr(browser, "_render_guarded", diagnostic_render)
    async with fixture_site({"/secret": (200, {}, "secret")}, forbidden_hits) as forbidden:
        routes = {
            "/robots.txt": (200, {"Content-Type": "text/plain"}, "User-agent: *\nDisallow: /deny"),
            "/redirect": (302, {"Location": forbidden + "/secret"}, ""),
            "/allowed-redirect": (302, {"Location": "/final"}, ""),
            "/deny-redirect": (302, {"Location": "/deny"}, ""),
            "/deny": (200, {}, "must never arrive"),
            "/final": (200, {}, "<html><body>final page</body></html>"),
            "/page": (
                200,
                {},
                f"""<html><body><p id="content">before</p>
                <iframe src="{forbidden}/secret"></iframe>
                <script src="{forbidden}/secret"></script>
                <script>
                  fetch('{forbidden}/secret').catch(() => {{}});
                  new WebSocket('{forbidden.replace("http:", "ws:")}/secret');
                  document.getElementById('content').textContent = 'JavaScript rendered';
                  navigator.serviceWorker.register('/worker.js').catch(() => {{}});
                </script></body></html>""",
            ),
            "/worker.js": (
                200,
                {"Content-Type": "application/javascript"},
                f"fetch('{forbidden}/secret');",
            ),
        }
        async with fixture_site(routes, main_hits) as allowed:

            async def fixture_guard(url: str, *, allow_internal: bool = False) -> None:
                # Admit exactly the fixture origin; all other requests use the real public policy.
                if urlparse(url).netloc == urlparse(allowed).netloc:
                    return
                await ensure_fetch_url_resolves_allowed(url)

            monkeypatch.setattr(browser, "ensure_fetch_url_resolves_allowed", fixture_guard)
            kwargs = {
                "concurrency": ConcurrencyConfig(timeout_seconds=10),
                "browser_config": BrowserConfig(),
                "fetch_config": FetchConfig(),
            }
            page = await browser.fetch_rendered_html(allowed + "/page", **kwargs)
            assert page is not None, "\n".join(render_errors)
            assert "JavaScript rendered" in page.html
            assert forbidden_hits == []
            assert "/worker.js" not in main_hits
            with pytest.raises(FetchUrlError):
                await browser.fetch_rendered_html(allowed + "/redirect", **kwargs)
            assert forbidden_hits == []
            from solocrawl.core.fetch.robots import RobotsDisallowedError

            with pytest.raises(RobotsDisallowedError):
                await browser.fetch_rendered_html(allowed + "/deny-redirect", **kwargs)
            assert "/deny" not in main_hits
            render_errors.clear()
            final = await browser.fetch_rendered_html(allowed + "/allowed-redirect", **kwargs)
            assert final is not None, "\n".join(render_errors)
            assert final.url == allowed + "/final"


async def test_chromium_internal_override_is_explicit() -> None:
    hits: list[str] = []
    async with fixture_site({"/page": (200, {}, "<p>trusted local page</p>")}, hits) as url:
        with pytest.raises(FetchUrlError):
            await browser.fetch_rendered_html(
                url + "/page", concurrency=ConcurrencyConfig(), browser_config=BrowserConfig()
            )
        page = await browser.fetch_rendered_html(
            url + "/page",
            concurrency=ConcurrencyConfig(),
            browser_config=BrowserConfig(),
            allow_internal_urls=True,
            fetch_config=FetchConfig(respect_robots=False),
        )
        assert page is not None, "Install Chromium: python -m playwright install chromium"
        assert page.url == url + "/page"
