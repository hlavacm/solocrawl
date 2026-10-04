"""Check real FastMCP clients in process and through the stdio entry point."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from solocrawl.core.models import FetchResult, PackageInfo, SearchResult
from solocrawl.mcp import server

pytestmark = pytest.mark.mcp
EXPECTED_INPUTS = {
    "web_search": {"query", "limit", "sources"},
    "scrape": {"url"},
    "research": {"query", "depth"},
    "package_version": {"name", "ecosystem", "constraint", "allow_prerelease"},
    "list_providers": {"provider_type"},
}


async def test_mcp_schemas_and_all_five_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "select_providers", lambda config: [object()])
    monkeypatch.setattr(
        server,
        "federated_search",
        AsyncMock(
            return_value=[
                SearchResult(
                    title="Fixture",
                    url="https://example.com",
                    snippet="text",
                    source="fixture",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        server,
        "fetch",
        AsyncMock(
            return_value=FetchResult(
                url="https://example.com",
                content="Fixture content",
                content_type="text/plain",
                status=200,
            )
        ),
    )
    monkeypatch.setattr(server, "run_research", AsyncMock(return_value=[]))
    provider = type(
        "Provider",
        (),
        {
            "get_package": AsyncMock(
                return_value=PackageInfo(
                    name="example",
                    ecosystem="pypi",
                    latest="1.0.0",
                )
            )
        },
    )()
    monkeypatch.setattr(server, "select_provider_for_ecosystem", lambda *args: provider)
    async with Client(server.create_server()) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == set(EXPECTED_INPUTS)
        for tool in tools:
            assert set(tool.input_schema["properties"]) == EXPECTED_INPUTS[tool.name]
        calls = [
            ("web_search", {"query": "test"}, "Fixture"),
            ("scrape", {"url": "https://example.com"}, "Fixture content"),
            ("research", {"query": "test"}, "No results"),
            ("package_version", {"name": "example", "ecosystem": "pypi"}, "latest: 1.0.0"),
            ("list_providers", {}, "Search providers"),
        ]
        for name, arguments, expected in calls:
            result = await client.call_tool(name, arguments)
            assert not result.is_error
            assert expected in result.data
            assert all(content.type == "text" for content in result.content)


async def test_mcp_configuration_error_is_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOLOCRAWL_TIMEOUT_SECONDS", "nan")
    async with Client(server.create_server()) as client:
        result = await client.call_tool("web_search", {"query": "test"}, raise_on_error=False)
    assert result.is_error
    assert "SOLOCRAWL_TIMEOUT_SECONDS" in str(result.content)


async def test_stdio_protocol_and_shutdown(tmp_path) -> None:
    # Running outside the checkout also verifies that an editable install resolves the entry point.
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "solocrawl.mcp"],
        cwd=str(tmp_path),
        keep_alive=False,
        env={
            "PYTHON_DOTENV_DISABLED": "1",
            "FASTMCP_MCP_CAMELCASE_COMPAT": "false",
            "SOLOCRAWL_LOG_LEVEL": "ERROR",
            "SOLOCRAWL_LOG_FILE": "",
        },
    )
    async with Client(transport, timeout=20) as client:
        assert {tool.name for tool in await client.list_tools()} == set(EXPECTED_INPUTS)
        result = await client.call_tool("list_providers", {})
        assert "Package providers" in result.data
        blocked = await client.call_tool("scrape", {"url": "http://127.0.0.1/secret"})
        assert "error:" in blocked.data
    assert transport._session is None
