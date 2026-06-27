"""Tests for HTML extraction and fallback behavior."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from solocrawl.core.extract import extract_html, is_content_too_short
from solocrawl.core.extract.extractor import PageMetadata, extract_metadata

_META_HTML = (
    "<html><head><title>My Title</title>"
    '<meta name="author" content="Jane Doe">'
    '<meta property="article:published_time" content="2024-05-01">'
    '<meta property="og:site_name" content="Example Site">'
    "</head><body><article><h1>Heading</h1><p>"
    + ("Lorem ipsum dolor sit amet. " * 30)
    + "</p></article></body></html>"
)


def test_extract_article_returns_markdown(read_fixture) -> None:
    html = read_fixture("article.html")
    content = extract_html(html, url="https://example.com/article")

    assert "Understanding Async HTTP Clients" in content
    assert "async http clients reuse connections" in content.lower()
    assert not is_content_too_short(content)


def test_extract_falls_back_when_trafilatura_is_empty(read_fixture) -> None:
    html = read_fixture("degenerate.html")

    with patch(
        "solocrawl.core.extract.extractor.trafilatura.extract",
        return_value=None,
    ):
        content = extract_html(html, url="https://example.com/degenerate")

    assert len(content.strip()) >= 80
    assert "boilerplate" in content.lower() or "short" in content.lower()


def test_extract_uses_body_text_as_last_resort(read_fixture) -> None:
    html = read_fixture("body_fallback.html")

    with (
        patch("solocrawl.core.extract.extractor.trafilatura.extract", return_value=None),
        patch(
            "solocrawl.core.extract.extractor.Document",
            side_effect=RuntimeError("readability failed"),
        ),
    ):
        content = extract_html(html)

    assert "standalone paragraph" in content.lower()
    assert not is_content_too_short(content)


def test_extract_metadata_reads_common_fields() -> None:
    meta = extract_metadata(_META_HTML, url="https://example.com/article")

    assert meta.author == "Jane Doe"
    assert meta.date == "2024-05-01"
    assert meta.site_name == "Example Site"
    assert meta.title  # title is present (exact value depends on trafilatura heuristics)


def test_extract_metadata_handles_empty_html() -> None:
    assert extract_metadata("") == PageMetadata()
    assert extract_metadata("   ") == PageMetadata()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", True),
        ("   ", True),
        ("short", True),
        ("x" * 79, True),
        ("word " * 20, False),
    ],
)
def test_is_content_too_short(text: str, expected: bool) -> None:
    assert is_content_too_short(text) is expected
