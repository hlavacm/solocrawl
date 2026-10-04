"""Shared helpers for package registry providers."""

from __future__ import annotations

from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.resolver import (
    ConstraintParser,
    VersionEntry,
    VersionNormalizer,
    parse_semver_constraint,
    previous_versions,
    resolve_latest,
)


class PackageNotFoundError(Exception):
    """Raised when a package does not exist in a registry."""


def build_package_info(
    *,
    name: str,
    ecosystem: str,
    versions: list[VersionEntry],
    repository: str | None = None,
    homepage: str | None = None,
    changelog: str | None = None,
    constraint: str | None = None,
    allow_prerelease: bool = False,
    constraint_parser: ConstraintParser | None = None,
    version_normalizer: VersionNormalizer | None = None,
) -> PackageInfo:
    """Build ``PackageInfo`` with a resolved latest version."""
    version_strings = [entry.version for entry in versions if not entry.yanked]
    use_semver = constraint_parser is parse_semver_constraint and ecosystem not in {
        "maven",
        "nuget",
        "rubygems",
    }
    latest = resolve_latest(
        versions,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=constraint_parser,
        version_normalizer=version_normalizer,
        semver=use_semver,
    )
    if latest is None:
        msg = f"no matching version found for {name!r}"
        raise PackageNotFoundError(msg)

    return PackageInfo(
        name=name,
        ecosystem=ecosystem,
        latest=latest,
        versions=previous_versions(
            version_strings,
            latest=latest,
            count=5,
            allow_prerelease=allow_prerelease,
            semver=use_semver,
            version_normalizer=version_normalizer,
        ),
        repository=repository,
        homepage=homepage,
        changelog=changelog,
    )
