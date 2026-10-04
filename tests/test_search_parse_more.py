"""Edge-case coverage for search payload parsers (guards and skip branches)."""

from __future__ import annotations

from solocrawl.core.search.providers.github import _parse_github_payload
from solocrawl.core.search.providers.hackernews import _parse_hn_payload
from solocrawl.core.search.providers.mdn import _parse_mdn_payload
from solocrawl.core.search.providers.pubmed import _extract_ids, _parse_pubmed_summary
from solocrawl.core.search.providers.searxng import _parse_searxng_payload
from solocrawl.core.search.providers.stackexchange import _parse_search_response
from solocrawl.core.search.providers.wikidata import _parse_wikidata_payload


def test_parsers_reject_non_dict_payload() -> None:
    assert _parse_github_payload("nope", limit=5) == []
    assert _parse_mdn_payload("nope", limit=5) == []
    assert _parse_searxng_payload("nope", limit=5) == []
    assert _parse_hn_payload("nope", limit=5) == []
    assert _parse_wikidata_payload("nope", limit=5) == []
    assert _parse_search_response("nope", limit=5) == []
    assert _extract_ids("nope", limit=5) == []
    assert _parse_pubmed_summary("nope", ids=[]) == []


def test_github_skips_malformed_items() -> None:
    payload = {
        "items": [
            "not-a-dict",
            {"full_name": 123},  # non-str name
            {"full_name": "a/b"},  # missing html_url
            {"full_name": "ok/repo", "html_url": "https://github.com/ok/repo"},
        ]
    }
    results = _parse_github_payload(payload, limit=5)
    assert [r.title for r in results] == ["ok/repo"]


def test_mdn_skips_malformed_items() -> None:
    payload = {"documents": ["x", {"title": "T"}, {"title": "Ok", "mdn_url": "/a"}]}
    results = _parse_mdn_payload(payload, limit=5)
    assert [r.title for r in results] == ["Ok"]


def test_searxng_skips_malformed_items() -> None:
    payload = {"results": ["x", {"title": "T"}, {"title": "Ok", "url": "https://e.example"}]}
    results = _parse_searxng_payload(payload, limit=5)
    assert [r.title for r in results] == ["Ok"]


def test_pubmed_extract_ids_happy() -> None:
    payload = {"esearchresult": {"idlist": ["1", "2"]}}
    assert _extract_ids(payload, limit=5) == ["1", "2"]
