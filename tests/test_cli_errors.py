"""Coverage for CLI error/edge branches across subcommands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from solocrawl.cli import main
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.resolver import InvalidConstraintError


# --- research ---------------------------------------------------------------
def test_research_empty_query(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main.main(["research", "   "])
    assert exc.value.code == 1
    assert "empty" in capsys.readouterr().err


def test_research_bad_depth(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main.main(["research", "q", "--depth", "0"])
    assert exc.value.code == 1
    assert "depth" in capsys.readouterr().err


def test_research_no_results(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("solocrawl.cli.research.research", new=AsyncMock(return_value=[])),
        patch("solocrawl.cli.research.close_client", new=AsyncMock(return_value=None)),
        patch("solocrawl.cli.research.close_browser", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc,
    ):
        main.main(["research", "q"])
    assert exc.value.code == 0
    assert "No results" in capsys.readouterr().err


# --- batch ------------------------------------------------------------------
def test_batch_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main.main(["batch", "--from-file", "/no/such/file.txt"])
    assert exc.value.code == 1
    assert "cannot read" in capsys.readouterr().err


def test_batch_out_dir_is_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    clash = tmp_path / "afile"
    clash.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main.main(["batch", "https://a.example", "--out-dir", str(clash)])
    assert exc.value.code == 1
    assert "cannot create" in capsys.readouterr().err


# --- scrape -----------------------------------------------------------------
def test_scrape_robots_disallowed(capsys: pytest.CaptureFixture[str]) -> None:
    from solocrawl.core.fetch import RobotsDisallowedError

    with (
        patch(
            "solocrawl.cli.scrape.fetch",
            new=AsyncMock(side_effect=RobotsDisallowedError("robots.txt disallows")),
        ),
        patch("solocrawl.cli.scrape.close_client", new=AsyncMock(return_value=None)),
        patch("solocrawl.cli.scrape.close_browser", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc,
    ):
        main.main(["scrape", "https://example.com/x"])
    assert exc.value.code == 1
    assert "error:" in capsys.readouterr().err


# --- package ----------------------------------------------------------------
def test_package_no_provider(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("solocrawl.cli.package.select_provider_for_ecosystem", return_value=None),
        patch("solocrawl.cli.package.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc,
    ):
        main.main(["package", "x", "--ecosystem", "pypi"])
    assert exc.value.code == 1


def test_package_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    class P:
        async def get_package(self, name, *, constraint=None, allow_prerelease=False):
            return PackageInfo(name=name, ecosystem="pypi", latest="1.2.3")

    with (
        patch("solocrawl.cli.package.select_provider_for_ecosystem", return_value=P()),
        patch("solocrawl.cli.package.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc,
    ):
        main.main(["package", "requests", "--ecosystem", "pypi", "--json"])
    assert exc.value.code == 0
    assert '"latest": "1.2.3"' in capsys.readouterr().out


def test_package_constraint_error(capsys: pytest.CaptureFixture[str]) -> None:
    class P:
        async def get_package(self, name, *, constraint=None, allow_prerelease=False):
            raise InvalidConstraintError("bad")

    with (
        patch("solocrawl.cli.package.select_provider_for_ecosystem", return_value=P()),
        patch("solocrawl.cli.package.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc,
    ):
        main.main(["package", "x", "--ecosystem", "pypi", "--constraint", "???"])
    assert exc.value.code == 1


def test_package_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    class P:
        async def get_package(self, name, *, constraint=None, allow_prerelease=False):
            raise PackageNotFoundError("nope")

    with (
        patch("solocrawl.cli.package.select_provider_for_ecosystem", return_value=P()),
        patch("solocrawl.cli.package.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc,
    ):
        main.main(["package", "x", "--ecosystem", "pypi"])
    assert exc.value.code == 1


# --- search -----------------------------------------------------------------
def test_search_bad_limit(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main.main(["search", "q", "--limit", "0"])
    assert exc.value.code == 1
    assert "limit" in capsys.readouterr().err


def test_search_no_results(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("solocrawl.cli.search.select_providers", return_value=[object()]),
        patch("solocrawl.cli.search.federated_search", new=AsyncMock(return_value=[])),
        patch("solocrawl.cli.search.close_client", new=AsyncMock(return_value=None)),
        patch("solocrawl.cli.search.close_browser", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc,
    ):
        main.main(["search", "q"])
    assert exc.value.code == 0
    assert "No results" in capsys.readouterr().err
