"""A few more small edge tests for safety margin above 96% coverage."""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest

import solocrawl.core.search.registry as search_registry
from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.fetch.url_validation import validate_fetch_url
from solocrawl.core.models import SearchResult
from solocrawl.core.packages.providers.nuget import NuGetProvider


# --- url validation blocked hosts ------------------------------------------
def test_validate_fetch_url_blocked_and_missing_host() -> None:
    assert validate_fetch_url("http://:8080/") is not None  # no hostname
    assert validate_fetch_url("http://service.local/") is not None  # .local suffix
    assert validate_fetch_url("http://[::1]/") is not None  # IPv6 loopback
    assert validate_fetch_url("https://example.com/ok") is None


# --- search registry duplicate guard ---------------------------------------
class _DummySearch:
    name = "demo"
    zero_config = True

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return []


@pytest.fixture
def isolated_search_registry() -> Generator[None]:
    saved = dict(search_registry._REGISTRY)
    search_registry._REGISTRY.clear()
    try:
        yield
    finally:
        search_registry._REGISTRY.clear()
        search_registry._REGISTRY.update(saved)


def test_search_registry_rejects_duplicate(isolated_search_registry: None) -> None:
    search_registry.register("demo")(_DummySearch)
    with pytest.raises(ValueError, match="already registered"):
        search_registry.register("demo")(_DummySearch)


# --- nuget inline registration page + skip branches ------------------------
async def test_nuget_inline_and_skipped_pages() -> None:
    index = {"versions": ["1.0.0"]}
    registration = {
        "items": [
            "not-a-dict",  # skipped
            # inline items page (no extra fetch needed)
            {"items": [{"catalogEntry": {"version": "1.0.0", "listed": True}}]},
            # @id page that 404s -> kept as-is
            {"@id": "https://api.nuget.org/v3/registration5-gz-semver2/pkg/page/x.json"},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "flatcontainer" in url:
            return httpx.Response(200, json=index, request=request)
        if "/page/x.json" in url:
            return httpx.Response(404, request=request)
        if "registration" in url:
            return httpx.Response(200, json=registration, request=request)
        return httpx.Response(404, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    try:
        info = await NuGetProvider(config=Config()).get_package("Pkg")
        assert info.latest == "1.0.0"
    finally:
        await client.aclose()
