"""Tests for the ``solocrawl scrape`` CLI command."""

from __future__ import annotations

import argparse
from pathlib import Path

import httpx
import pytest

from solocrawl.cli import main as cli_main
from solocrawl.cli.scrape import _scrape
from solocrawl.core.fetch.client import set_client_for_testing


def _html_response(
    html: str,
    *,
    status: int = 200,
    content_type: str = "text/html; charset=utf-8",
    url: str = "https://example.com/",
) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"Content-Type": content_type},
        text=html,
        request=httpx.Request("GET", url),
    )


def test_main_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: solocrawl" in captured.out
    assert "scrape" in captured.out


def test_scrape_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main.main(["scrape", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Fetch a URL" in captured.out
    assert "--out" in captured.out
    assert "--force-browser" in captured.out


def test_main_without_command_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli_main.main([])

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "usage: solocrawl" in captured.out
    assert "scrape" in captured.out


async def test_scrape_prints_markdown_to_stdout(
    article_html: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _html_response(article_html, url=str(request.url))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    args = argparse_namespace(url="https://example.com/page")
    exit_code = await _scrape(args.url, out=args.out, force_browser=args.force_browser)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Understanding Async HTTP Clients" in captured.out
    assert captured.err == ""
    await client.aclose()


async def test_scrape_writes_markdown_to_file(
    article_html: str,
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _html_response(article_html, url=str(request.url))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    out_file = tmp_path / "out.md"
    args = argparse_namespace(url="https://example.com/page", out=out_file)
    exit_code = await _scrape(args.url, out=args.out, force_browser=args.force_browser)

    assert exit_code == 0
    assert "Understanding Async HTTP Clients" in out_file.read_text(encoding="utf-8")
    await client.aclose()


_META_PAGE = (
    "<html><head><title>Doc Title</title>"
    '<meta name="author" content="Jane Doe">'
    '<meta property="article:published_time" content="2024-05-01">'
    '<meta property="og:site_name" content="Example Site">'
    "</head><body><article><h1>Heading</h1><p>"
    + ("Lorem ipsum dolor sit amet consectetur. " * 30)
    + "</p></article></body></html>"
)


async def test_scrape_emits_front_matter_when_metadata_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _html_response(_META_PAGE, url=str(request.url))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    args = argparse_namespace(url="https://example.com/page")
    exit_code = await _scrape(args.url, out=args.out, force_browser=args.force_browser)

    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.startswith("---\n")
    assert 'author: "Jane Doe"' in out
    assert 'date: "2024-05-01"' in out
    assert "url: " in out
    await client.aclose()


async def test_scrape_invalid_url_reports_clear_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse_namespace(url="http://127.0.0.1/admin")
    exit_code = await _scrape(args.url, out=args.out, force_browser=args.force_browser)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "127.0.0.1" in captured.err
    assert captured.out == ""


async def test_scrape_network_error_reports_clear_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    args = argparse_namespace(url="https://example.com/unreachable")
    exit_code = await _scrape(args.url, out=args.out, force_browser=args.force_browser)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "error: network error:" in captured.err
    assert captured.out == ""
    await client.aclose()


async def test_scrape_http_error_reports_clear_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    args = argparse_namespace(url="https://example.com/missing")
    exit_code = await _scrape(args.url, out=args.out, force_browser=args.force_browser)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "error: HTTP 404" in captured.err
    assert captured.out == ""
    await client.aclose()


def argparse_namespace(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {"out": None, "force_browser": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)
