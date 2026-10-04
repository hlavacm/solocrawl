"""PyPI package provider."""

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
from solocrawl.core.packages.resolver import VersionEntry

logger = logging.getLogger(__name__)


@register("pypi", ecosystem="pypi", zero_config=True, configurable=True)
class PyPIProvider:
    """Fetch package metadata from PyPI."""

    name = "pypi"
    ecosystem = "pypi"
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
        """Return package metadata for a PyPI project."""
        package_name = name.strip()
        if not package_name:
            msg = "package name must not be empty"
            raise PackageNotFoundError(msg)

        url = f"https://pypi.org/pypi/{quote(package_name, safe='')}/json"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url)
            if response.status_code == 404:
                msg = f"package not found on PyPI: {package_name}"
                raise PackageNotFoundError(msg)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("pypi lookup failed for %r: %s", package_name, exc)
            msg = f"failed to fetch package from PyPI: {package_name}"
            raise PackageNotFoundError(msg) from exc

        return _parse_pypi_payload(
            package_name,
            payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_pypi_payload(
    name: str,
    payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    if not isinstance(payload, dict):
        msg = f"invalid PyPI response for {name!r}"
        raise PackageNotFoundError(msg)

    info = payload.get("info")
    releases = payload.get("releases")
    if not isinstance(info, dict) or not isinstance(releases, dict):
        msg = f"invalid PyPI response for {name!r}"
        raise PackageNotFoundError(msg)

    versions = _pypi_versions(releases)
    repository = _first_url(info, ("Source", "Repository", "Code"))
    homepage = _first_url(info, ("Homepage", "Home", "Website")) or info.get("home_page")
    homepage = homepage if isinstance(homepage, str) else None

    return build_package_info(
        name=name,
        ecosystem="pypi",
        versions=versions,
        repository=repository,
        homepage=homepage,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
    )


def _pypi_versions(releases: dict[str, Any]) -> list[VersionEntry]:
    versions: list[VersionEntry] = []
    for version, files in releases.items():
        if not isinstance(files, list) or not files:
            continue
        yanked = all(
            isinstance(file_info, dict) and file_info.get("yanked") is True for file_info in files
        )
        versions.append(VersionEntry(version, yanked=yanked))
    return versions


def _first_url(info: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    project_urls = info.get("project_urls")
    if isinstance(project_urls, dict):
        for key in keys:
            value = project_urls.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None
