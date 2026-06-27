"""Targeted coverage for remaining provider/registry/selector/server branches."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import solocrawl.core.packages.registry as pkg_registry
from solocrawl.config import Config, FetchConfig
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.fetch.fetcher import fetch
from solocrawl.core.models import FetchResult, PackageInfo, SearchResult
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.providers.maven import MavenProvider
from solocrawl.core.packages.providers.npm import _parse_npm_payload
from solocrawl.core.packages.providers.pub import _parse_pub_payload
from solocrawl.core.packages.selector import select_provider_for_ecosystem, select_providers
from solocrawl.mcp.server import scrape, web_search


# --- npm / pub helper branches ---------------------------------------------
def test_npm_fallback_metadata_and_string_repository() -> None:
    payload = {"versions": {"1.0.0": {"repository": "git+https://github.com/x/y.git"}}}
    info = _parse_npm_payload("p", payload, constraint=None, allow_prerelease=False)
    assert info.latest == "1.0.0"
    assert info.repository == "https://github.com/x/y"


def test_pub_skip_and_dict_repository() -> None:
    payload = {
        "versions": [
            "notdict",
            {"version": "1.0.0", "pubspec": {"repository": {"url": "https://github.com/x/y"}}},
        ]
    }
    info = _parse_pub_payload("p", payload, constraint=None, allow_prerelease=False)
    assert info.repository == "https://github.com/x/y"


def test_pub_without_pubspec_has_no_repository() -> None:
    payload = {"versions": [{"version": "1.0.0"}]}
    info = _parse_pub_payload("p", payload, constraint=None, allow_prerelease=False)
    assert info.repository is None


# --- maven format guard + network error ------------------------------------
async def test_maven_requires_colon() -> None:
    with pytest.raises(PackageNotFoundError):
        await MavenProvider(config=Config()).get_package("nocolon")


async def test_maven_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    try:
        with pytest.raises(PackageNotFoundError):
            await MavenProvider(config=Config()).get_package("org.example:lib")
    finally:
        await client.aclose()


# --- fetcher branches -------------------------------------------------------
async def test_fetch_retry_after_invalid_date(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("solocrawl.core.fetch.fetcher.asyncio.sleep", fake_sleep)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, headers={"Retry-After": "soon-ish"}, request=request)
        return httpx.Response(
            200, headers={"Content-Type": "text/plain"}, text="ok", request=request
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    config = Config(fetch=FetchConfig(respect_robots=False))
    result = await fetch("https://example.com/x", config=config)
    assert result.content == "ok"
    assert sleeps  # fell back to backoff because the date was unparseable
    await client.aclose()


async def test_fetch_too_short_html_without_browser() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/html"},
            text="<html><body>hi</body></html>",
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    config = Config(fetch=FetchConfig(respect_robots=False))
    result = await fetch("https://example.com/short", config=config)
    assert result.status == 200  # short content returned as-is (no browser fallback available)
    await client.aclose()


# --- package registry -------------------------------------------------------
@pytest.fixture
def isolated_pkg_registry() -> Generator[None]:
    saved = dict(pkg_registry._REGISTRY)
    pkg_registry._REGISTRY.clear()
    try:
        yield
    finally:
        pkg_registry._REGISTRY.clear()
        pkg_registry._REGISTRY.update(saved)


class _DummyPkg:
    name = "demo"
    ecosystem = "demo"
    zero_config = False

    async def get_package(self, name, *, constraint=None, allow_prerelease=False) -> PackageInfo:
        return PackageInfo(name=name, ecosystem="demo", latest="1.0.0")


def test_pkg_registry_duplicate_and_lookup(isolated_pkg_registry: None) -> None:
    pkg_registry.register("demo", ecosystem="demo", required_env_key="DEMO_KEY")(_DummyPkg)
    with pytest.raises(ValueError, match="already registered"):
        pkg_registry.register("demo", ecosystem="demo")(_DummyPkg)

    assert pkg_registry.get_registration("demo") is not None
    assert pkg_registry.get_registration_for_ecosystem("demo") is not None
    assert pkg_registry.get_registration_for_ecosystem("nope") is None


def test_pkg_selector_optin_gating(isolated_pkg_registry: None) -> None:
    pkg_registry.register("demo", ecosystem="demo", required_env_key="DEMO_KEY")(_DummyPkg)

    # enabled but no key -> not selected
    cfg = Config(enabled_providers=frozenset({"demo"}))
    assert select_providers(cfg, env={}) == []
    # enabled + key -> selected
    selected = select_providers(cfg, env={"DEMO_KEY": "x"})
    assert [p.name for p in selected] == ["demo"]
    # ecosystem lookup miss
    assert select_provider_for_ecosystem("missing", Config(), env={}) is None


# --- mcp server extra branches ---------------------------------------------
def test_providers_for_search_filters_sources() -> None:
    from solocrawl.mcp.server import _providers_for_search

    class _P:
        def __init__(self, name: str) -> None:
            self.name = name

    with patch(
        "solocrawl.mcp.server.select_providers", return_value=[_P("wikipedia"), _P("other")]
    ):
        result = _providers_for_search(Config(), ["wikipedia"])
    assert [p.name for p in result] == ["wikipedia"]

    with patch("solocrawl.mcp.server.select_providers", return_value=[_P("a")]):
        assert len(_providers_for_search(Config(), None)) == 1


async def test_web_search_happy() -> None:
    hits = [SearchResult(title="W", url="https://w.example", snippet="s", source="wikipedia")]
    with (
        patch("solocrawl.mcp.server._providers_for_search", return_value=[object()]),
        patch("solocrawl.mcp.server.federated_search", new=AsyncMock(return_value=hits)),
    ):
        out = await web_search("q")
    assert "W" in out


async def test_scrape_url_only_header() -> None:
    result = FetchResult(
        url="https://example.com/x",
        content="Just body",
        content_type="text/html",
        status=200,
    )
    with patch("solocrawl.mcp.server.fetch", new=AsyncMock(return_value=result)):
        out = await scrape("https://example.com/x")
    assert "# https://example.com/x" in out
    assert "Just body" in out
