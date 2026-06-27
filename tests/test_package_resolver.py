"""Tests for the package version resolver."""

from __future__ import annotations

import pytest

from solocrawl.core.packages.resolver import (
    InvalidConstraintError,
    VersionEntry,
    normalize_go_module_version,
    parse_semver_constraint,
    previous_versions,
    resolve_latest,
)


def test_resolve_latest_picks_highest_stable() -> None:
    versions = ["1.0.0", "1.2.0", "1.1.0", "2.0.0rc1"]

    assert resolve_latest(versions) == "1.2.0"
    assert resolve_latest(versions, allow_prerelease=True) == "2.0.0rc1"


def test_resolve_latest_excludes_prerelease_by_default() -> None:
    versions = ["1.0.0", "2.0.0b1", "1.5.0"]

    assert resolve_latest(versions) == "1.5.0"
    assert resolve_latest(versions, allow_prerelease=True) == "2.0.0b1"


def test_resolve_latest_with_constraint() -> None:
    versions = ["4.0.0", "4.2.1", "4.2.9", "5.0.0", "4.3.0"]

    assert resolve_latest(versions, constraint=">=4.2,<5") == "4.3.0"


def test_resolve_latest_excludes_yanked() -> None:
    versions = [
        VersionEntry("1.0.0"),
        VersionEntry("1.1.0", yanked=True),
        VersionEntry("1.2.0"),
    ]

    assert resolve_latest(versions) == "1.2.0"


def test_resolve_latest_empty_input() -> None:
    assert resolve_latest([]) is None


def test_resolve_latest_normalizes_go_module_versions() -> None:
    versions = ["v1.8.0", "v1.8.1", "v1.9.0-beta.1"]
    assert (
        resolve_latest(
            versions,
            constraint=">=1.8.0,<1.8.1",
            version_normalizer=normalize_go_module_version,
        )
        == "v1.8.0"
    )


def test_previous_versions_returns_older_releases() -> None:
    versions = ["1.0.0", "1.1.0", "1.2.0", "2.0.0"]

    previous = previous_versions(versions, latest="2.0.0", count=2)

    assert previous == ["1.2.0", "1.1.0"]


_NPM_VERSIONS = ["1.0.0", "1.2.0", "1.2.5", "1.3.0", "2.0.0", "2.1.0", "0.9.0"]


@pytest.mark.parametrize(
    ("constraint", "expected"),
    [
        ("^1.2.0", "1.3.0"),  # caret: >=1.2.0 <2.0.0
        ("^1.2", "1.3.0"),
        ("^2", "2.1.0"),  # >=2.0.0 <3.0.0
        ("~1.2.0", "1.2.5"),  # tilde: >=1.2.0 <1.3.0
        ("~1.2", "1.2.5"),
        ("1.x", "1.3.0"),  # wildcard: >=1.0.0 <2.0.0
        ("1.2.x", "1.2.5"),
        ("*", "2.1.0"),  # any
        ("1.2.0", "1.2.0"),  # exact
        (">=1.2,<2", "1.3.0"),  # comparator range still works
        (">= 1.2.0 <1.3.0", "1.2.5"),  # space-separated AND with spaced operator
        ("^1.2.0 || ^2.0.0", "2.1.0"),  # OR of ranges picks highest match
        ("1.2.0 - 1.3.0", "1.3.0"),  # hyphen range, inclusive
    ],
)
def test_parse_semver_constraint_resolves(constraint: str, expected: str) -> None:
    resolved = resolve_latest(
        _NPM_VERSIONS,
        constraint=constraint,
        constraint_parser=parse_semver_constraint,
    )
    assert resolved == expected


def test_parse_semver_constraint_caret_below_one_is_minor_pinned() -> None:
    # ^0.2.x := >=0.2.0 <0.3.0 — must not jump to 0.9.0.
    versions = ["0.1.0", "0.2.0", "0.2.9", "0.3.0", "0.9.0"]
    resolved = resolve_latest(
        versions,
        constraint="^0.2.0",
        constraint_parser=parse_semver_constraint,
    )
    assert resolved == "0.2.9"


@pytest.mark.parametrize("constraint", ["not-a-version", "^abc", "~", "~x"])
def test_parse_semver_constraint_rejects_garbage(constraint: str) -> None:
    with pytest.raises(InvalidConstraintError):
        parse_semver_constraint(constraint)
