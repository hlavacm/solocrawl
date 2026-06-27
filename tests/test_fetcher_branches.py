"""Branch-coverage tests for the fetch path (retries, content types, browser)."""

from __future__ import annotations

import httpx
import pytest

from solocrawl.config import BrowserConfig, Config, FetchConfig, load_config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.fetch.fetcher import fetch

_NO_ROBOTS = {"SOLOCRAWL_RESPECT_ROBOTS": "false"}


async def test_fetch_retries_on_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("solocrawl.core.fetch.fetcher.asyncio.sleep", fake_sleep)

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("flaky", request=request)
        return httpx.Response(
            200, headers={"Content-Type": "text/plain"}, text="done", request=request
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    config = load_config(env={"SOLOCRAWL_MAX_RETRIES": "2", **_NO_ROBOTS})
    result = await fetch("https://example.com/flaky", config=config)

    assert result.content == "done"
    assert calls == 2
    assert sleeps  # a backoff sleep happened
    await client.aclose()


async def test_fetch_retry_after_http_date(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("solocrawl.core.fetch.fetcher.asyncio.sleep", fake_sleep)

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"},
                request=request,
            )
        return httpx.Response(
            200, headers={"Content-Type": "text/plain"}, text="ok", request=request
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    config = load_config(env={"SOLOCRAWL_MAX_RETRIES": "2", **_NO_ROBOTS})
    result = await fetch("https://example.com/rl", config=config)

    assert result.content == "ok"
    assert sleeps and sleeps[0] > 0
    await client.aclose()


async def test_fetch_unsupported_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"Content-Type": "image/png"}, content=b"\x89PNG\r\n", request=request
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    config = Config(fetch=FetchConfig(respect_robots=False))
    result = await fetch("https://example.com/i.png", config=config)

    assert "Unsupported content type" in result.content
    await client.aclose()


async def test_fetch_invalid_json_returns_raw() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"Content-Type": "application/json"}, text="{bad json", request=request
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    config = Config(fetch=FetchConfig(respect_robots=False))
    result = await fetch("https://example.com/d.json", config=config)

    assert result.content == "{bad json"
    await client.aclose()


async def test_fetch_force_browser_disabled_message() -> None:
    config = Config(
        browser=BrowserConfig(allowed=False),
        fetch=FetchConfig(respect_robots=False),
    )
    result = await fetch("https://example.com/js", force_browser=True, config=config)

    assert result.status == 0
    assert "disabled" in result.content.lower()
