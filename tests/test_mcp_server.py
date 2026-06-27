"""Tests for the MCP server tool registration and wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from solocrawl.core.models import PackageInfo, SearchResult
from solocrawl.mcp.server import (
    MAX_MCP_OUTPUT_CHARS,
    package_version,
    research,
    scrape,
    web_search,
)


@pytest.mark.asyncio
async def test_web_search_tool_returns_formatted_results() -> None:
    results = [
        SearchResult(
            title="Example",
            url="https://example.com",
            snippet="snippet",
            source="wikipedia",
        )
    ]
    with (
        patch("solocrawl.mcp.server.select_providers", return_value=[object()]),
        patch(
            "solocrawl.mcp.server.federated_search",
            new=AsyncMock(return_value=results),
        ),
        patch("solocrawl.mcp.server.close_client", new=AsyncMock(return_value=None)),
    ):
        output = await web_search("python", limit=1)

    assert "Example" in output
    assert "https://example.com" in output


@pytest.mark.asyncio
async def test_web_search_tool_caps_limit() -> None:
    with (
        patch("solocrawl.mcp.server.select_providers", return_value=[object()]),
        patch(
            "solocrawl.mcp.server.federated_search",
            new=AsyncMock(return_value=[]),
        ) as search,
    ):
        await web_search("python", limit=999)

    assert search.await_args is not None
    assert search.await_args.kwargs["limit"] == 20


@pytest.mark.asyncio
async def test_scrape_tool_returns_markdown() -> None:
    from solocrawl.core.models import FetchResult

    fetch_result = FetchResult(
        url="https://example.com",
        content="# Title\n\nBody",
        content_type="text/markdown",
        status=200,
    )
    with (
        patch("solocrawl.mcp.server.fetch", new=AsyncMock(return_value=fetch_result)),
        patch("solocrawl.mcp.server.close_client", new=AsyncMock(return_value=None)),
        patch("solocrawl.mcp.server.close_browser", new=AsyncMock(return_value=None)),
    ):
        output = await scrape("https://example.com")

    assert "Body" in output


@pytest.mark.asyncio
async def test_scrape_tool_truncates_large_output() -> None:
    from solocrawl.core.models import FetchResult

    fetch_result = FetchResult(
        url="https://example.com",
        content="x" * (MAX_MCP_OUTPUT_CHARS + 100),
        content_type="text/markdown",
        status=200,
    )
    with patch("solocrawl.mcp.server.fetch", new=AsyncMock(return_value=fetch_result)):
        output = await scrape("https://example.com")

    assert "[truncated " in output
    assert len(output) < MAX_MCP_OUTPUT_CHARS + 100


@pytest.mark.asyncio
async def test_scrape_tool_blocks_internal_url() -> None:
    with (
        patch("solocrawl.mcp.server.close_client", new=AsyncMock(return_value=None)),
        patch("solocrawl.mcp.server.close_browser", new=AsyncMock(return_value=None)),
    ):
        output = await scrape("http://127.0.0.1/admin")

    assert "error:" in output
    assert "127.0.0.1" in output


@pytest.mark.asyncio
async def test_scrape_tool_keeps_runtime_alive_across_calls() -> None:
    from solocrawl.core.models import FetchResult

    fetch_result = FetchResult(
        url="https://example.com",
        content="Body",
        content_type="text/html",
        status=200,
    )
    close_client = AsyncMock(return_value=None)
    close_browser = AsyncMock(return_value=None)
    with (
        patch("solocrawl.mcp.server.fetch", new=AsyncMock(return_value=fetch_result)),
        patch("solocrawl.mcp.server.close_client", new=close_client),
        patch("solocrawl.mcp.server.close_browser", new=close_browser),
    ):
        await scrape("https://example.com")
        await scrape("https://example.com")

    # Cleanup is deferred to the server lifespan, so individual tool calls must
    # not tear down the shared client or browser.
    close_client.assert_not_awaited()
    close_browser.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifespan_cleans_up_runtime_on_shutdown() -> None:
    from solocrawl.mcp.server import _lifespan, mcp

    close_client = AsyncMock(return_value=None)
    close_browser = AsyncMock(return_value=None)
    with (
        patch("solocrawl.mcp.server.close_client", new=close_client),
        patch("solocrawl.mcp.server.close_browser", new=close_browser),
    ):
        async with _lifespan(mcp):
            close_client.assert_not_awaited()
            close_browser.assert_not_awaited()

    close_client.assert_awaited_once()
    close_browser.assert_awaited_once()


@pytest.mark.asyncio
async def test_package_version_tool_returns_metadata() -> None:
    class DummyProvider:
        ecosystem = "pypi"

        async def get_package(
            self,
            name: str,
            *,
            constraint: str | None = None,
            allow_prerelease: bool = False,
        ) -> PackageInfo:
            return PackageInfo(name=name, ecosystem="pypi", latest="2.32.3")

    with (
        patch(
            "solocrawl.mcp.server.select_provider_for_ecosystem",
            return_value=DummyProvider(),
        ),
        patch("solocrawl.mcp.server.close_client", new=AsyncMock(return_value=None)),
    ):
        output = await package_version("requests", "pypi")

    assert "latest: 2.32.3" in output


@pytest.mark.asyncio
async def test_research_tool_caps_depth() -> None:
    with (
        patch("solocrawl.mcp.server.run_research", new=AsyncMock(return_value=[])) as run,
        patch("solocrawl.mcp.server.research_to_markdown", return_value="# Research"),
    ):
        await research("python", depth=999)

    assert run.await_args is not None
    assert run.await_args.kwargs["depth"] == 8


@pytest.mark.asyncio
async def test_cleanup_runtime_closes_shared_resources() -> None:
    from unittest.mock import AsyncMock, patch

    from solocrawl.mcp import __main__ as mcp_main

    close_client = AsyncMock()
    close_browser = AsyncMock()
    with (
        patch("solocrawl.mcp.__main__.close_client", close_client),
        patch("solocrawl.mcp.__main__.close_browser", close_browser),
    ):
        await mcp_main._cleanup_runtime()

    close_client.assert_awaited_once()
    close_browser.assert_awaited_once()


def test_mcp_server_exposes_tools() -> None:
    import asyncio

    from solocrawl import __version__
    from solocrawl.mcp.server import REPO_URL, create_server

    server = create_server()
    assert server.name == "SoloCrawl"
    assert server.version == __version__
    assert server.website_url == REPO_URL
    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}
    assert {
        "web_search",
        "scrape",
        "package_version",
        "list_providers",
        "research",
    }.issubset(tool_names)
