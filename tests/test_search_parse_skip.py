"""Skip-branch coverage for search provider parsers."""

from __future__ import annotations

from solocrawl.core.search.providers.arxiv import _parse_arxiv_atom
from solocrawl.core.search.providers.hackernews import _parse_hn_payload
from solocrawl.core.search.providers.pubmed import _extract_ids, _parse_pubmed_summary
from solocrawl.core.search.providers.stackexchange import _parse_search_response as _se_parse
from solocrawl.core.search.providers.wikidata import _parse_wikidata_payload
from solocrawl.core.search.providers.wikipedia import _parse_search_response as _wiki_parse


def test_wikidata_branches() -> None:
    assert _parse_wikidata_payload({"search": "notlist"}, limit=5) == []
    payload = {
        "search": [
            "x",  # non-dict
            {"description": "d"},  # no label
            {"label": "Proto", "url": "//www.wikidata.org/wiki/Q1", "description": "d"},
            {"label": "FromId", "id": "Q2"},  # no url -> build from id
        ]
    }
    results = _parse_wikidata_payload(payload, limit=5)
    titles = [r.title for r in results]
    assert "Proto" in titles and "FromId" in titles
    proto = next(r for r in results if r.title == "Proto")
    assert proto.url.startswith("https://")
    from_id = next(r for r in results if r.title == "FromId")
    assert from_id.url.endswith("/Q2")


def test_wikipedia_branches() -> None:
    assert _wiki_parse("nope", wiki="en", limit=5) == []
    assert _wiki_parse({"query": "x"}, wiki="en", limit=5) == []
    assert _wiki_parse({"query": {}}, wiki="en", limit=5) == []
    payload = {"query": {"search": ["x", {"title": ""}, {"title": "Ok", "snippet": "<b>hi</b>"}]}}
    results = _wiki_parse(payload, wiki="en", limit=5)
    assert [r.title for r in results] == ["Ok"]


def test_stackexchange_branches() -> None:
    assert _se_parse({"items": "notlist"}, limit=5) == []
    payload = {
        "items": [
            "x",
            {"title": 1, "link": "u"},
            {"title": "", "link": "u"},
            {"title": "Short", "link": "https://so.example/1", "body": "", "score": "bad"},
            {"title": "Long", "link": "https://so.example/2", "body": "<p>" + "x " * 400 + "</p>"},
        ]
    }
    results = _se_parse(payload, limit=5)
    titles = [r.title for r in results]
    assert titles == ["Short", "Long"]
    assert results[1].snippet.endswith("...")  # long body truncated


def test_pubmed_branches() -> None:
    assert _extract_ids({"esearchresult": "x"}, limit=5) == []
    assert _extract_ids({"esearchresult": {"idlist": "x"}}, limit=5) == []
    assert _parse_pubmed_summary({"result": "x"}, ids=["1"]) == []
    payload = {"result": {"1": "notdict", "2": {"title": ""}, "3": {"title": "Ok"}}}
    results = _parse_pubmed_summary(payload, ids=["1", "2", "3"])
    assert [r.title for r in results] == ["Ok"]


def test_arxiv_branches() -> None:
    assert _parse_arxiv_atom("not <xml", limit=5) == []
    atom = (
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<entry><id>http://arxiv.org/abs/1234</id><title>Paper</title><summary>S</summary></entry>"
        "<entry><title>NoUrl</title></entry>"
        "</feed>"
    )
    results = _parse_arxiv_atom(atom, limit=5)
    assert [r.title for r in results] == ["Paper"]
    assert results[0].url.endswith("/abs/1234")


def test_hackernews_branches() -> None:
    assert _parse_hn_payload({"hits": "notlist"}, limit=5) == []
    payload = {
        "hits": ["x", {"title": "T"}, {"title": "Ok", "url": "https://e.example", "points": 5}]
    }
    results = _parse_hn_payload(payload, limit=5)
    assert [r.title for r in results] == ["Ok"]
