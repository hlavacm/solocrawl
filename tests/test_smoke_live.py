"""Opt-in live checks; each provider is tested before federation can hide failures."""

from __future__ import annotations

import argparse
import os

import pytest

from solocrawl.cli.batch import _batch
from solocrawl.config import BrowserConfig, Config
from solocrawl.core.fetch import fetch
from solocrawl.core.packages import providers as _package_providers  # noqa: F401
from solocrawl.core.packages import select_provider_for_ecosystem
from solocrawl.core.research import research
from solocrawl.core.search import federated_search, select_providers
from solocrawl.core.search import providers as _search_providers  # noqa: F401

pytestmark = pytest.mark.live
SEARCH_NAMES = [
    "wikipedia",
    "duckduckgo",
    "stackexchange",
    "wikidata",
    "hackernews",
    "arxiv",
    "pubmed",
    "github",
    "mdn",
    "searxng",
]
PACKAGES = {
    "pypi": "requests",
    "npm": "react",
    "packagist": "monolog/monolog",
    "crates": "serde",
    "nuget": "Newtonsoft.Json",
    "maven": "org.apache.commons:commons-lang3",
    "rubygems": "rails",
    "go": "github.com/Azure/azure-sdk-for-go/sdk/azcore",
    "pub": "collection",
    "swift": "apple/swift-argument-parser",
}


@pytest.mark.parametrize("name", SEARCH_NAMES, ids=SEARCH_NAMES)
async def test_search_provider_live(name: str) -> None:
    if name == "searxng" and not os.environ.get("SOLOCRAWL_SEARXNG_URL"):
        pytest.skip("SOLOCRAWL_SEARXNG_URL is not configured")
    config = Config(enabled_providers=frozenset({name}))
    providers = [provider for provider in select_providers(config) if provider.name == name]
    assert len(providers) == 1
    query = "cancer" if name == "pubmed" else "python"
    results = await providers[0].search(query, limit=3)
    assert results, f"{name} returned no results (check endpoint / diagnostics)"
    assert all(result.url and result.title for result in results)


@pytest.mark.parametrize("ecosystem", list(PACKAGES), ids=list(PACKAGES))
async def test_package_provider_live(ecosystem: str) -> None:
    provider = select_provider_for_ecosystem(ecosystem, Config())
    assert provider is not None
    info = await provider.get_package(PACKAGES[ecosystem])
    assert info.latest
    assert info.ecosystem == ecosystem


async def test_federated_search_live() -> None:
    results = await federated_search(select_providers(Config()), "python asyncio", limit=3)
    assert results
    assert all(result.url for result in results)


async def test_fetch_live() -> None:
    result = await fetch("https://example.com", config=Config(browser=BrowserConfig(allowed=False)))
    assert result.status == 200
    assert result.content.strip()


async def test_research_live() -> None:
    documents = await research(
        "python asyncio", depth=2, config=Config(browser=BrowserConfig(allowed=False))
    )
    assert any(document.content for document in documents)


async def test_batch_live(capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(
        urls=["https://example.com", "https://www.python.org"],
        from_file=None,
        out_dir=None,
        force_browser=False,
    )
    assert await _batch(args) == 0
    assert "https://example.com" in capsys.readouterr().out
