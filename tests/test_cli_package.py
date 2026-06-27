"""Tests for the CLI package subcommand."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from solocrawl.cli import main
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.providers.base import PackageNotFoundError


class DummyProvider:
    name = "pypi"
    ecosystem = "pypi"
    zero_config = True

    async def get_package(
        self,
        name: str,
        *,
        constraint: str | None = None,
        allow_prerelease: bool = False,
    ) -> PackageInfo:
        latest = "4.2.9" if constraint else "5.0.0"
        return PackageInfo(
            name=name,
            ecosystem="pypi",
            latest=latest,
            versions=["4.2.9", "4.2.0"],
            repository="https://github.com/example/repo",
            homepage="https://example.com",
        )


def test_package_prints_info(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch(
            "solocrawl.cli.package.select_provider_for_ecosystem",
            return_value=DummyProvider(),
        ),
        patch("solocrawl.cli.package.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(["package", "requests", "--ecosystem", "pypi"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "latest: 5.0.0" in captured.out
    assert "repository: https://github.com/example/repo" in captured.out


def test_package_constraint(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch(
            "solocrawl.cli.package.select_provider_for_ecosystem",
            return_value=DummyProvider(),
        ),
        patch("solocrawl.cli.package.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(
            [
                "package",
                "requests",
                "--ecosystem",
                "pypi",
                "--constraint",
                ">=4.2,<5",
            ]
        )

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "latest: 4.2.9" in captured.out


def test_package_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch(
            "solocrawl.cli.package.select_provider_for_ecosystem",
            return_value=DummyProvider(),
        ),
        patch("solocrawl.cli.package.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(["package", "requests", "--ecosystem", "pypi", "--json"])

    assert exc_info.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["latest"] == "5.0.0"


def test_package_not_found(capsys: pytest.CaptureFixture[str]) -> None:
    class MissingProvider(DummyProvider):
        async def get_package(
            self,
            name: str,
            *,
            constraint: str | None = None,
            allow_prerelease: bool = False,
        ) -> PackageInfo:
            msg = "package not found on PyPI: missing"
            raise PackageNotFoundError(msg)

    with (
        patch(
            "solocrawl.cli.package.select_provider_for_ecosystem",
            return_value=MissingProvider(),
        ),
        patch("solocrawl.cli.package.close_client", new=AsyncMock(return_value=None)),
        pytest.raises(SystemExit) as exc_info,
    ):
        main.main(["package", "missing", "--ecosystem", "pypi"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "not found" in captured.err.lower()
