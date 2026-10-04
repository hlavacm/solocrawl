"""Tests for opt-in search providers."""

from __future__ import annotations

import json
from collections.abc import Generator

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.search import clear_registry, select_providers
from solocrawl.core.search import registry as search_registry
from solocrawl.core.search.providers import arxiv as arxiv_module
from solocrawl.core.search.providers import hackernews as hn_module
from solocrawl.core.search.providers import pubmed as pubmed_module
from solocrawl.core.search.providers import wikidata as wikidata_module
from solocrawl.core.search.providers.arxiv import ArxivProvider, _parse_arxiv_atom
from solocrawl.core.search.providers.hackernews import HackerNewsProvider, _parse_hn_payload
from solocrawl.core.search.providers.pubmed import PubMedProvider, _parse_pubmed_summary
from solocrawl.core.search.providers.wikidata import WikidataProvider, _parse_wikidata_payload


@pytest.fixture(autouse=True)
def optin_providers_registered() -> Generator[None]:
    saved = dict(search_registry._REGISTRY)
    clear_registry()
    wikidata_module.register("wikidata", configurable=True)(WikidataProvider)
    hn_module.register("hackernews", configurable=True)(HackerNewsProvider)
    arxiv_module.register("arxiv", configurable=True)(ArxivProvider)
    pubmed_module.register("pubmed", configurable=True)(PubMedProvider)
    yield
    clear_registry()
    search_registry._REGISTRY.update(saved)


def test_wikidata_parse_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("wikidata_search.json"))
    results = _parse_wikidata_payload(payload, limit=5)
    assert results
    assert results[0].source == "wikidata"
    assert "programming language" in results[1].snippet


def test_hackernews_parse_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("hackernews_search.json"))
    results = _parse_hn_payload(payload, limit=5)
    assert len(results) == 2
    assert results[0].score == 256.0


def test_arxiv_parse_fixture(read_fixture) -> None:
    body = read_fixture("arxiv_search.xml")
    results = _parse_arxiv_atom(body, limit=5)
    assert len(results) == 2
    assert "Attention" in results[0].title


def test_pubmed_parse_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("pubmed_esummary.json"))
    results = _parse_pubmed_summary(payload, ids=["12345", "67890"])
    assert len(results) == 2
    assert "pubmed.ncbi.nlm.nih.gov" in results[0].url


def test_opt_in_providers_not_in_default_selection() -> None:
    providers = select_providers(Config(), env={})
    names = {provider.name for provider in providers}
    assert "wikidata" not in names
    assert "hackernews" not in names


def test_opt_in_providers_enabled_via_config() -> None:
    config = Config(enabled_providers=frozenset({"arxiv", "hackernews"}))
    providers = select_providers(config, env={})
    names = {provider.name for provider in providers}
    assert "arxiv" in names
    assert "hackernews" in names


async def test_wikidata_search_uses_shared_client(read_fixture) -> None:
    fixture_body = read_fixture("wikidata_search.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json.loads(fixture_body), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = WikidataProvider(config=Config())
    results = await provider.search("python", limit=2)
    assert len(results) == 2
    await client.aclose()


async def test_pubmed_two_phase_search(read_fixture) -> None:
    esearch = read_fixture("pubmed_esearch.json")
    esummary = read_fixture("pubmed_esummary.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if "esearch.fcgi" in str(request.url):
            return httpx.Response(200, json=json.loads(esearch), request=request)
        return httpx.Response(200, json=json.loads(esummary), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = PubMedProvider(config=Config())
    results = await provider.search("async programming", limit=2)
    assert len(results) == 2
    await client.aclose()
