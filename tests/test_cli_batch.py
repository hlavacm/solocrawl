"""Tests for the ``solocrawl batch`` CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from solocrawl.cli import main
from solocrawl.core.models import FetchResult


async def _fake_fetch(url: str, *, force_browser: bool = False) -> FetchResult:
    if "bad" in url:
        raise RuntimeError("nope")
    return FetchResult(url=url, content=f"content {url}", content_type="text/html", status=200)


def _patches():
    return (
        patch("solocrawl.cli.batch.fetch", new=AsyncMock(side_effect=_fake_fetch)),
        patch("solocrawl.cli.batch.close_client", new=AsyncMock(return_value=None)),
        patch("solocrawl.cli.batch.close_browser", new=AsyncMock(return_value=None)),
    )


def test_batch_prints_each_result(capsys: pytest.CaptureFixture[str]) -> None:
    fetch_p, client_p, browser_p = _patches()
    with fetch_p, client_p, browser_p, pytest.raises(SystemExit) as exc_info:
        main.main(["batch", "https://a.example", "https://b.example"])

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "content https://a.example" in out
    assert "content https://b.example" in out


def test_batch_writes_to_out_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fetch_p, client_p, browser_p = _patches()
    with fetch_p, client_p, browser_p, pytest.raises(SystemExit) as exc_info:
        main.main(["batch", "https://a.example", "https://b.example", "--out-dir", str(tmp_path)])

    assert exc_info.value.code == 0
    files = list(tmp_path.glob("*.md"))
    assert len(files) == 2


def test_batch_reports_failures(capsys: pytest.CaptureFixture[str]) -> None:
    fetch_p, client_p, browser_p = _patches()
    with fetch_p, client_p, browser_p, pytest.raises(SystemExit) as exc_info:
        main.main(["batch", "https://a.example", "https://bad.example"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "content https://a.example" in captured.out
    assert "bad.example" in captured.err


def test_batch_reads_from_file(tmp_path: Path) -> None:
    url_file = tmp_path / "urls.txt"
    url_file.write_text("https://a.example\n# a comment\n\nhttps://b.example\n", encoding="utf-8")

    fetch_p, client_p, browser_p = _patches()
    out_dir = tmp_path / "out"
    with fetch_p, client_p, browser_p, pytest.raises(SystemExit) as exc_info:
        main.main(["batch", "--from-file", str(url_file), "--out-dir", str(out_dir)])

    assert exc_info.value.code == 0
    assert len(list(out_dir.glob("*.md"))) == 2


def test_batch_without_urls_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main.main(["batch"])

    assert exc_info.value.code == 1
    assert "no URLs" in capsys.readouterr().err


def test_batch_write_failure_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch_p, client_p, browser_p = _patches()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    out_dir.chmod(0o500)

    with fetch_p, client_p, browser_p, pytest.raises(SystemExit) as exc_info:
        main.main(["batch", "https://a.example", "--out-dir", str(out_dir)])

    assert exc_info.value.code == 1
    assert "cannot write" in capsys.readouterr().err
