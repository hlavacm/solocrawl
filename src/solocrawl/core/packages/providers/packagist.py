"""Packagist package provider."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.providers.base import PackageNotFoundError, build_package_info
from solocrawl.core.packages.registry import register
from solocrawl.core.packages.resolver import VersionEntry, parse_semver_constraint, resolve_latest

logger = logging.getLogger(__name__)


@register("packagist", ecosystem="packagist", zero_config=True, configurable=True)
class PackagistProvider:
    """Fetch package metadata from Packagist."""

    name = "packagist"
    ecosystem = "packagist"
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
        """Return package metadata for a Composer package."""
        package_name = name.strip()
        if "/" not in package_name:
            msg = "packagist package names must use vendor/package format"
            raise PackageNotFoundError(msg)

        vendor, package = package_name.split("/", maxsplit=1)
        url = (
            f"https://repo.packagist.org/p2/{quote(vendor, safe='')}/{quote(package, safe='')}.json"
        )

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url)
            if response.status_code == 404:
                msg = f"package not found on Packagist: {package_name}"
                raise PackageNotFoundError(msg)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("packagist lookup failed for %r: %s", package_name, exc)
            msg = f"failed to fetch package from Packagist: {package_name}"
            raise PackageNotFoundError(msg) from exc

        return _parse_packagist_payload(
            package_name,
            payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_packagist_payload(
    name: str,
    payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    if not isinstance(payload, dict):
        msg = f"invalid Packagist response for {name!r}"
        raise PackageNotFoundError(msg)

    packages = payload.get("packages")
    if not isinstance(packages, dict):
        msg = f"package not found on Packagist: {name}"
        raise PackageNotFoundError(msg)

    versions_list = packages.get(name)
    if not isinstance(versions_list, list) or not versions_list:
        msg = f"package not found on Packagist: {name}"
        raise PackageNotFoundError(msg)

    versions = [
        VersionEntry(str(item["version"]))
        for item in versions_list
        if isinstance(item, dict) and isinstance(item.get("version"), str)
    ]
    latest = resolve_latest(
        versions,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )
    latest_meta = _metadata_for_version(versions_list, latest)
    repository = _repository_url(latest_meta)
    homepage = latest_meta.get("homepage")
    homepage = homepage if isinstance(homepage, str) else None

    return build_package_info(
        name=name,
        ecosystem="packagist",
        versions=versions,
        repository=repository,
        homepage=homepage,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )


def _metadata_for_version(versions_list: list[object], latest: str | None) -> dict[str, Any]:
    if latest is None:
        return {}
    for item in versions_list:
        if isinstance(item, dict) and item.get("version") == latest:
            return item
    return {}


def _repository_url(metadata: dict[str, Any]) -> str | None:
    source = metadata.get("source")
    if isinstance(source, dict):
        url = source.get("url")
        if isinstance(url, str):
            return url.removesuffix(".git")
    return None
