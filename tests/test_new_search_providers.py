"""Tests for the opt-in GitHub / MDN / Reddit / SearXNG search providers."""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest

import solocrawl.core.search.registry as search_registry
from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.search import select_providers
from solocrawl.core.search.providers.github import GitHubProvider, _parse_github_payload
from solocrawl.core.search.providers.mdn import MdnProvider, _parse_mdn_payload
from solocrawl.core.search.providers.reddit import RedditProvider, _parse_reddit_payload
from solocrawl.core.search.providers.searxng import SearxngProvider, _parse_searxng_payload


def test_parse_github_payload() -> None:
    payload = {
        "items": [
            {
                "full_name": "psf/requests",
                "html_url": "https://github.com/psf/requests",
                "description": "A simple, yet elegant HTTP library.",
                "stargazers_count": 52000,
            }
        ]
    }
    results = _parse_github_payload(payload, limit=5)

    assert results[0].title == "psf/requests"
    assert results[0].url == "https://github.com/psf/requests"
    assert results[0].source == "github"
    assert results[0].score == 52000.0


def test_parse_mdn_payload_makes_absolute_url() -> None:
    payload = {
        "documents": [
            {
                "title": "Fetch API",
                "mdn_url": "/en-US/docs/Web/API/Fetch_API",
                "summary": "The Fetch API provides an interface for fetching resources.",
                "score": 12.3,
            }
        ]
    }
    results = _parse_mdn_payload(payload, limit=5)

    assert results[0].url == "https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API"
    assert results[0].source == "mdn"


def test_parse_reddit_payload_uses_permalink() -> None:
    payload = {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "Best asyncio patterns?",
                        "permalink": "/r/Python/comments/abc/best_asyncio/",
                        "url": "https://example.com/external",
                        "selftext": "x" * 500,
                        "score": 42,
                    }
                }
            ]
        }
    }
    results = _parse_reddit_payload(payload, limit=5)

    assert results[0].url == "https://www.reddit.com/r/Python/comments/abc/best_asyncio/"
    assert len(results[0].snippet) == 300
    assert results[0].score == 42.0


def test_parse_searxng_payload() -> None:
    payload = {
        "results": [
            {
                "title": "Result",
                "url": "https://example.com",
                "content": "snippet text",
                "score": 1.0,
            }
        ]
    }
    results = _parse_searxng_payload(payload, limit=5)

    assert results[0].title == "Result"
    assert results[0].url == "https://example.com"
    assert results[0].source == "searxng"


async def test_github_provider_fetches_results() -> None:
    payload = {
        "items": [
            {
                "full_name": "psf/requests",
                "html_url": "https://github.com/psf/requests",
                "description": "HTTP for Humans",
                "stargazers_count": 100,
            }
        ]
    }
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json=payload, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = GitHubProvider(config=Config())
    results = await provider.search("requests", limit=3)

    assert results[0].title == "psf/requests"
    assert "api.github.com/search/repositories" in requests[0]
    await client.aclose()


async def test_searxng_returns_empty_without_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOLOCRAWL_SEARXNG_URL", raising=False)
    provider = SearxngProvider(config=Config())

    assert await provider.search("anything") == []


@pytest.fixture
def only_new_providers() -> Generator[None]:
    saved = dict(search_registry._REGISTRY)
    search_registry._REGISTRY.clear()
    search_registry.register("github")(GitHubProvider)
    search_registry.register("mdn")(MdnProvider)
    search_registry.register("reddit")(RedditProvider)
    search_registry.register("searxng", required_env_key="SOLOCRAWL_SEARXNG_URL")(SearxngProvider)
    try:
        yield
    finally:
        search_registry._REGISTRY.clear()
        search_registry._REGISTRY.update(saved)


def test_opt_in_providers_are_gated(only_new_providers: None) -> None:
    # Nothing enabled -> no opt-in providers selected.
    assert select_providers(Config(), env={}) == []

    # github enabled (no key needed).
    enabled = Config(enabled_providers=frozenset({"github"}))
    names = {provider.name for provider in select_providers(enabled, env={})}
    assert names == {"github"}

    # searxng enabled but needs its base URL to actually activate.
    searxng_cfg = Config(enabled_providers=frozenset({"searxng"}))
    assert select_providers(searxng_cfg, env={}) == []
    activated = select_providers(
        searxng_cfg, env={"SOLOCRAWL_SEARXNG_URL": "http://localhost:8888"}
    )
    assert {provider.name for provider in activated} == {"searxng"}
