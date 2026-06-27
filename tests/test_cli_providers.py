"""Tests for the providers subcommand and the MCP list_providers tool."""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest

import solocrawl.core.packages.registry as pkg_registry
import solocrawl.core.search.registry as search_registry
from solocrawl.cli import main
from solocrawl.core.models import PackageInfo, SearchResult
from solocrawl.mcp.server import list_providers


class _DummySearch:
    name = "demo_search"
    zero_config = True

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return []


class _DummyKeyed:
    name = "demo_keyed"
    zero_config = False

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return []


class _DummyPackage:
    name = "demo_pkg"
    ecosystem = "demo"
    zero_config = True

    async def get_package(
        self,
        name: str,
        *,
        constraint: str | None = None,
        allow_prerelease: bool = False,
    ) -> PackageInfo:
        return PackageInfo(name=name, ecosystem="demo", latest="1.0.0")


@pytest.fixture
def dummy_registries() -> Generator[None]:
    """Replace both registries with a known set, restoring the originals afterwards."""
    saved_search = dict(search_registry._REGISTRY)
    saved_pkg = dict(pkg_registry._REGISTRY)
    search_registry._REGISTRY.clear()
    pkg_registry._REGISTRY.clear()

    search_registry.register("demo_search", zero_config=True)(_DummySearch)
    search_registry.register("demo_keyed", required_env_key="SOLOCRAWL_DEMO_KEY")(_DummyKeyed)
    pkg_registry.register("demo_pkg", ecosystem="demo", zero_config=True)(_DummyPackage)
    try:
        yield
    finally:
        search_registry._REGISTRY.clear()
        search_registry._REGISTRY.update(saved_search)
        pkg_registry._REGISTRY.clear()
        pkg_registry._REGISTRY.update(saved_pkg)


def test_providers_text_output(dummy_registries: None, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main.main(["providers"])

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "Search providers:" in out
    assert "Package providers:" in out
    assert "demo_search" in out
    assert "default" in out
    assert "opt-in" in out
    assert "(requires SOLOCRAWL_DEMO_KEY)" in out
    assert "demo_pkg (demo)" in out


def test_providers_json_output(dummy_registries: None, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main.main(["providers", "--json"])

    assert exc_info.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    search_names = {item["name"] for item in payload["search"]}
    assert search_names == {"demo_search", "demo_keyed"}
    assert payload["package"][0]["name"] == "demo_pkg"
    assert payload["package"][0]["ecosystem"] == "demo"


def test_providers_type_filter(dummy_registries: None, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main.main(["providers", "--type", "search", "--json"])

    assert exc_info.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["search"]
    assert payload["package"] == []


@pytest.mark.asyncio
async def test_mcp_list_providers_tool(dummy_registries: None) -> None:
    output = await list_providers()

    assert "Search providers:" in output
    assert "demo_search" in output
    assert "Package providers:" in output
    assert "demo_pkg (demo)" in output
