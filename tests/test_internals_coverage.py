"""Coverage for federation, fusion, selector, client, and ddgs helpers."""

from __future__ import annotations

from typing import cast

import httpx
import pytest

from solocrawl.config import ConcurrencyConfig, Config
from solocrawl.core.fetch.client import (
    get_client,
    resolve_user_agent,
    set_client_for_testing,
)
from solocrawl.core.models import SearchResult
from solocrawl.core.search.federation import federated_search
from solocrawl.core.search.fusion import fuse_results, normalize_url
from solocrawl.core.search.protocol import SearchProvider
from solocrawl.core.search.providers.duckduckgo import _map_ddgs_results, _run_ddgs_text
from solocrawl.core.search.selector import select_providers


class _Failing:
    name = "failing"

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        raise RuntimeError("boom")


class _BadType:
    name = "badtype"

    async def search(self, query: str, *, limit: int = 5):  # noqa: ANN201
        return "not a list"


class _Good:
    name = "good"

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return [SearchResult(title="T", url="https://e.example", snippet="s", source="good")]


async def test_federation_empty_and_zero_limit() -> None:
    good = cast(list[SearchProvider], [_Good()])
    assert await federated_search([], "q") == []
    assert await federated_search(good, "q", limit=0) == []


async def test_federation_degrades_over_bad_providers() -> None:
    providers = cast(list[SearchProvider], [_Failing(), _BadType(), _Good()])
    results = await federated_search(providers, "q", limit=3)
    assert len(results) == 1
    assert results[0].url == "https://e.example"


def test_normalize_url_strips_tracking_and_trailing_slash() -> None:
    a = normalize_url("https://e.example/path/?utm_source=x&keep=1")
    b = normalize_url("HTTPS://e.example/path?keep=1")
    assert a == b


def test_fuse_results_dedupes_and_labels_sources() -> None:
    fused = fuse_results(
        [
            (
                "a",
                [
                    SearchResult(
                        title="A", url="https://e.example/?utm_source=x", snippet="hi", source="a"
                    )
                ],
            ),
            (
                "b",
                [
                    SearchResult(
                        title="B", url="https://e.example", snippet="longer snippet", source="b"
                    )
                ],
            ),
        ],
        limit=5,
    )
    assert len(fused) == 1
    assert fused[0].source == "a+b"
    assert fused[0].snippet == "longer snippet"  # longer snippet wins


def test_selector_uses_init_env_when_env_none() -> None:
    # env=None triggers init_env() + os.environ; zero-config providers come back.
    providers = select_providers(Config())
    assert isinstance(providers, list)


async def test_resolve_user_agent_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOLOCRAWL_USER_AGENT", "CustomUA/1.0")
    assert resolve_user_agent() == "CustomUA/1.0"
    assert resolve_user_agent("Explicit/2.0") == "Explicit/2.0"


def _mock_client() -> httpx.AsyncClient:
    # A MockTransport client avoids building a real SSL context (sandbox-safe).
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, request=r))
    )


async def test_get_client_returns_injected_shared_client() -> None:
    injected = _mock_client()
    await set_client_for_testing(injected)
    returned = await get_client(ConcurrencyConfig())
    assert returned is injected
    await injected.aclose()
    await set_client_for_testing(None)


async def test_set_client_for_testing_closes_previous() -> None:
    first = _mock_client()
    await set_client_for_testing(first)
    second = _mock_client()
    await set_client_for_testing(second)  # should close `first`
    assert first.is_closed
    await second.aclose()
    await set_client_for_testing(None)


def test_map_ddgs_results_skips_malformed_items() -> None:
    raw = [
        {"title": "Good", "href": "https://e.example", "body": "ok"},
        {"title": "", "href": "https://e.example"},  # empty title -> skip
        {"title": 123, "href": "https://e.example"},  # non-str -> skip
    ]
    results = _map_ddgs_results(raw, limit=5)
    assert len(results) == 1
    assert results[0].title == "Good"


def test_run_ddgs_text_non_list(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeDDGS:
        def text(self, query: str, max_results: int) -> object:
            return None

    monkeypatch.setattr(
        "solocrawl.core.search.providers.duckduckgo._import_ddgs",
        lambda: _FakeDDGS,
    )
    assert _run_ddgs_text("q", limit=3) == []
