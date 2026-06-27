"""HTML to markdown extraction with a trafilatura-first fallback chain."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import trafilatura
from lxml import html as lxml_html
from markdownify import markdownify
from readability import Document

from solocrawl.core.extract.threshold import is_content_too_short

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PageMetadata:
    """Lightweight page metadata extracted alongside the markdown content."""

    title: str | None = None
    author: str | None = None
    date: str | None = None
    language: str | None = None
    site_name: str | None = None


def _clean_meta(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def extract_metadata(html: str, *, url: str | None = None) -> PageMetadata:
    """Extract title/author/date/language/site metadata from HTML (never raises)."""
    del url  # trafilatura derives metadata from the document itself
    if not html or not html.strip():
        return PageMetadata()

    try:
        doc = trafilatura.extract_metadata(html)
    except Exception:
        logger.debug("metadata extraction failed", exc_info=True)
        return PageMetadata()

    if doc is None:
        return PageMetadata()

    return PageMetadata(
        title=_clean_meta(getattr(doc, "title", None)),
        author=_clean_meta(getattr(doc, "author", None)),
        date=_clean_meta(getattr(doc, "date", None)),
        language=_clean_meta(getattr(doc, "language", None)),
        site_name=_clean_meta(getattr(doc, "sitename", None)),
    )


def extract_html(html: str, *, url: str | None = None) -> str:
    """Extract main content from HTML and return clean markdown."""
    if not html or not html.strip():
        return ""

    for name, extractor in (
        ("trafilatura", _extract_trafilatura),
        ("readability", _extract_readability),
        ("body_text", _extract_body_text),
    ):
        try:
            content = extractor(html, url=url)
        except Exception:
            logger.warning("extraction step %s failed", name, exc_info=True)
            content = ""

        if not is_content_too_short(content):
            return content.strip()

    return _extract_body_text(html, url=url).strip()


def _extract_trafilatura(html: str, *, url: str | None) -> str:
    content = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
    )
    return content or ""


def _extract_readability(html: str, *, url: str | None) -> str:
    del url
    document = Document(html)
    summary_html = document.summary()
    if not summary_html:
        return ""
    return markdownify(summary_html, heading_style="ATX").strip()


def _extract_body_text(html: str, *, url: str | None) -> str:
    del url
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return _strip_tags_fallback(html)

    body = tree.find(".//body")
    node = body if body is not None else tree
    text = " ".join(node.itertext())
    return re.sub(r"\s+", " ", text).strip()


def _strip_tags_fallback(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    return re.sub(r"\s+", " ", text).strip()
