"""Swift package provider.

Swift packages have no classic version registry: releases are git tags (semantic
versions) on the package's repository. This provider resolves versions from the
GitHub tags API for a ``owner/repo`` identifier (the common case, and what the
Swift Package Index itself indexes from).
"""

from __future__ import annotations

import logging

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.providers.base import PackageNotFoundError, build_package_info
from solocrawl.core.packages.registry import register
from solocrawl.core.packages.resolver import VersionEntry, parse_semver_constraint

logger = logging.getLogger(__name__)

_GITHUB_HEADERS = {"Accept": "application/vnd.github+json"}


@register("swift", ecosystem="swift", zero_config=True)
class SwiftProvider:
    """Resolve Swift package versions from a repository's git tags (GitHub)."""

    name = "swift"
    ecosystem = "swift"
    zero_config = True

    def __init__(self, *, config: Config | None = None) -> None:
        self._config = load_config() if config is None else config

    async def get_package(
        self,
        name: str,
        *,
        constraint: str | None = None,
        allow_prerelease: bool = False,
    ) -> PackageInfo:
        """Return version metadata for a Swift package identified by ``owner/repo``."""
        owner, repo = _parse_identifier(name)
        url = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=100"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url, headers=_GITHUB_HEADERS)
            if response.status_code == 404:
                msg = f"Swift package repository not found: {owner}/{repo}"
                raise PackageNotFoundError(msg)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Swift (GitHub tags) lookup failed for %r: %s", name, exc)
            msg = f"failed to fetch tags for Swift package: {owner}/{repo}"
            raise PackageNotFoundError(msg) from exc

        return _parse_tags_payload(
            owner,
            repo,
            payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_identifier(name: str) -> tuple[str, str]:
    cleaned = name.strip()
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    cleaned = cleaned.strip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]

    parts = cleaned.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        msg = f"Swift package name must be 'owner/repo' (got {name!r})"
        raise PackageNotFoundError(msg)
    return parts[0], parts[1]


def _parse_tags_payload(
    owner: str,
    repo: str,
    payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    if not isinstance(payload, list):
        msg = f"invalid GitHub tags response for {owner}/{repo}"
        raise PackageNotFoundError(msg)

    versions = _tag_versions(payload)
    if not versions:
        msg = f"no version tags found for Swift package: {owner}/{repo}"
        raise PackageNotFoundError(msg)

    return build_package_info(
        name=f"{owner}/{repo}",
        ecosystem="swift",
        versions=versions,
        repository=f"https://github.com/{owner}/{repo}",
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )


def _tag_versions(payload: list[object]) -> list[VersionEntry]:
    versions: list[VersionEntry] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        tag = item.get("name")
        if not isinstance(tag, str):
            continue
        if _looks_like_version(tag):
            versions.append(VersionEntry(tag))
    return versions


def _looks_like_version(tag: str) -> bool:
    core = tag.lstrip("vV")
    return bool(core) and core[0].isdigit()
