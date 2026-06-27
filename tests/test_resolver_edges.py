"""Edge-case coverage for the version resolver."""

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


def test_pep440_invalid_constraint_raises() -> None:
    with pytest.raises(InvalidConstraintError):
        resolve_latest(["1.0.0"], constraint="!!!nonsense")


def test_semver_empty_constraint_raises() -> None:
    with pytest.raises(InvalidConstraintError):
        parse_semver_constraint("")


def test_semver_comparator_with_bad_version_raises() -> None:
    with pytest.raises(InvalidConstraintError):
        parse_semver_constraint(">=abc")


def test_caret_all_zero_pins_patch() -> None:
    versions = ["0.0.3", "0.0.4", "0.1.0"]
    resolved = resolve_latest(
        versions, constraint="^0.0.3", constraint_parser=parse_semver_constraint
    )
    assert resolved == "0.0.3"


def test_tilde_single_component() -> None:
    versions = ["1.5.0", "2.0.0"]
    resolved = resolve_latest(versions, constraint="~1", constraint_parser=parse_semver_constraint)
    assert resolved == "1.5.0"


def test_previous_versions_with_invalid_latest_returns_empty() -> None:
    assert previous_versions(["1.0.0"], latest="not-a-version") == []


def test_previous_versions_skips_yanked_and_prerelease() -> None:
    versions = [
        VersionEntry("1.0.0"),
        VersionEntry("1.1.0", yanked=True),
        VersionEntry("1.2.0b1"),
        VersionEntry("0.9.0"),
    ]
    assert previous_versions(versions, latest="2.0.0", count=5) == ["1.0.0", "0.9.0"]


def test_normalize_go_module_version_without_v_prefix() -> None:
    assert normalize_go_module_version("1.2.3") == "1.2.3"
    assert normalize_go_module_version("v1.2.3") == "1.2.3"
