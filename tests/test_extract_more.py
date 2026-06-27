"""Edge coverage for metadata extraction."""

from __future__ import annotations

import pytest

from solocrawl.core.extract.extractor import PageMetadata, extract_metadata


def test_extract_metadata_doc_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "solocrawl.core.extract.extractor.trafilatura.extract_metadata",
        lambda html: None,
    )
    assert extract_metadata("<html></html>") == PageMetadata()


def test_extract_metadata_failure_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(html: str) -> object:
        raise RuntimeError("nope")

    monkeypatch.setattr(
        "solocrawl.core.extract.extractor.trafilatura.extract_metadata",
        boom,
    )
    assert extract_metadata("<html>x</html>") == PageMetadata()


def test_extract_metadata_minimal_no_crash() -> None:
    meta = extract_metadata("<html><body><p>hello world</p></body></html>")
    assert isinstance(meta, PageMetadata)
