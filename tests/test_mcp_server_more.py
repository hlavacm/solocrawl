"""Branch-coverage tests for MCP server tool error paths and extra tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx

from solocrawl.core.fetch import RobotsDisallowedError
from solocrawl.core.models import FetchResult
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.resolver import InvalidConstraintError
from solocrawl.core.research import ResearchDocument
from solocrawl.mcp.server import (
    list_providers,
    package_version,
    research,
    scrape,
    web_search,
)


async def test_web_search_no_providers() -> None:
    with patch("solocrawl.mcp.server._providers_for_search", return_value=[]):
        out = await web_search("q")
    assert "No search providers" in out


async def test_web_search_no_results() -> None:
    with (
        patch("solocrawl.mcp.server._providers_for_search", return_value=[object()]),
        patch("solocrawl.mcp.server.federated_search", new=AsyncMock(return_value=[])),
    ):
        out = await web_search("q")
    assert "No search results" in out


async def test_package_version_no_provider() -> None:
    with patch("solocrawl.mcp.server.select_provider_for_ecosystem", return_value=None):
        out = await package_version("x", "unknown")
    assert "No provider available" in out


async def test_package_version_invalid_constraint() -> None:
    class P:
        async def get_package(self, name, *, constraint=None, allow_prerelease=False):
            raise InvalidConstraintError("bad constraint")

    with patch("solocrawl.mcp.server.select_provider_for_ecosystem", return_value=P()):
        out = await package_version("x", "pypi", constraint="???")
    assert "error:" in out


async def test_package_version_not_found() -> None:
    class P:
        async def get_package(self, name, *, constraint=None, allow_prerelease=False):
            raise PackageNotFoundError("nope")

    with patch("solocrawl.mcp.server.select_provider_for_ecosystem", return_value=P()):
        out = await package_version("x", "pypi")
    assert "nope" in out


async def test_scrape_robots_disallowed() -> None:
    with patch(
        "solocrawl.mcp.server.fetch",
        new=AsyncMock(side_effect=RobotsDisallowedError("robots.txt disallows")),
    ):
        out = await scrape("https://example.com/x")
    assert "error:" in out and "robots" in out.lower()


async def test_scrape_http_status_error() -> None:
    request = httpx.Request("GET", "https://example.com/x")
    response = httpx.Response(404, request=request)
    err = httpx.HTTPStatusError("404", request=request, response=response)
    with patch("solocrawl.mcp.server.fetch", new=AsyncMock(side_effect=err)):
        out = await scrape("https://example.com/x")
    assert "HTTP 404" in out


async def test_scrape_request_error() -> None:
    err = httpx.ConnectError("boom", request=httpx.Request("GET", "https://example.com/x"))
    with patch("solocrawl.mcp.server.fetch", new=AsyncMock(side_effect=err)):
        out = await scrape("https://example.com/x")
    assert "network error" in out


async def test_scrape_with_metadata_header() -> None:
    result = FetchResult(
        url="https://example.com/x",
        content="Body text",
        content_type="text/html",
        status=200,
        title="My Page",
        author="Jane",
        date="2024-01-01",
    )
    with patch("solocrawl.mcp.server.fetch", new=AsyncMock(return_value=result)):
        out = await scrape("https://example.com/x")
    assert "# My Page" in out
    assert "Author: Jane" in out
    assert "Body text" in out


async def test_list_providers_package_only_and_unknown() -> None:
    package_out = await list_providers("package")
    assert "Package providers:" in package_out
    assert "Search providers:" not in package_out
    assert "Unknown provider_type" in await list_providers("bogus")


async def test_research_tool_returns_markdown() -> None:
    docs = [
        ResearchDocument(title="A", url="https://a.example", source="wikipedia", content="body")
    ]
    with patch("solocrawl.mcp.server.run_research", new=AsyncMock(return_value=docs)):
        out = await research("python", depth=1)
    assert "# Research: python" in out
    assert "## 1. A" in out
