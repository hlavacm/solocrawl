"""RubyGems package provider."""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.providers.base import PackageNotFoundError, build_package_info
from solocrawl.core.packages.registry import register
from solocrawl.core.packages.resolver import VersionEntry, parse_semver_constraint

logger = logging.getLogger(__name__)


@register("rubygems", ecosystem="rubygems", zero_config=True)
class RubyGemsProvider:
    """Fetch package metadata from RubyGems.org."""

    name = "rubygems"
    ecosystem = "rubygems"
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
        """Return package metadata for a Ruby gem."""
        package_name = name.strip()
        if not package_name:
            msg = "package name must not be empty"
            raise PackageNotFoundError(msg)

        quoted_name = quote(package_name, safe="")
        gem_url = f"https://rubygems.org/api/v1/gems/{quoted_name}.json"
        versions_url = f"https://rubygems.org/api/v1/versions/{quoted_name}.json"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            gem_response, versions_response = (
                await client.get(gem_url),
                await client.get(versions_url),
            )
            if gem_response.status_code == 404 or versions_response.status_code == 404:
                msg = f"package not found on RubyGems: {package_name}"
                raise PackageNotFoundError(msg)
            gem_response.raise_for_status()
            versions_response.raise_for_status()
            gem_payload = gem_response.json()
            versions_payload = versions_response.json()
        except httpx.HTTPError as exc:
            logger.warning("rubygems lookup failed for %r: %s", package_name, exc)
            msg = f"failed to fetch package from RubyGems: {package_name}"
            raise PackageNotFoundError(msg) from exc

        return _parse_rubygems_payload(
            package_name,
            gem_payload,
            versions_payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_rubygems_payload(
    name: str,
    gem_payload: object,
    versions_payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    if not isinstance(gem_payload, dict):
        msg = f"invalid RubyGems response for {name!r}"
        raise PackageNotFoundError(msg)
    if not isinstance(versions_payload, list) or not versions_payload:
        msg = f"package not found on RubyGems: {name}"
        raise PackageNotFoundError(msg)

    versions = _ruby_versions(versions_payload)
    repository = _optional_url(gem_payload.get("source_code_uri"))
    homepage = _optional_url(gem_payload.get("homepage_uri"))

    return build_package_info(
        name=name,
        ecosystem="rubygems",
        versions=versions,
        repository=repository,
        homepage=homepage,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )


def _ruby_versions(versions_payload: list[object]) -> list[VersionEntry]:
    versions: list[VersionEntry] = []
    for item in versions_payload:
        if not isinstance(item, dict):
            continue
        if item.get("platform") not in (None, "ruby"):
            continue
        number = item.get("number")
        if isinstance(number, str):
            versions.append(VersionEntry(number))
    return versions


def _optional_url(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
