"""pub.dev package provider."""

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
from solocrawl.core.packages.resolver import VersionEntry, parse_semver_constraint

logger = logging.getLogger(__name__)


@register("pub", ecosystem="pub", zero_config=True, configurable=True)
class PubProvider:
    """Fetch package metadata from pub.dev."""

    name = "pub"
    ecosystem = "pub"
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
        """Return package metadata for a Dart/Flutter package."""
        package_name = name.strip()
        if not package_name:
            msg = "package name must not be empty"
            raise PackageNotFoundError(msg)

        url = f"https://pub.dev/api/packages/{quote(package_name, safe='')}"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url)
            if response.status_code == 404:
                msg = f"package not found on pub.dev: {package_name}"
                raise PackageNotFoundError(msg)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("pub.dev lookup failed for %r: %s", package_name, exc)
            msg = f"failed to fetch package from pub.dev: {package_name}"
            raise PackageNotFoundError(msg) from exc

        return _parse_pub_payload(
            package_name,
            payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_pub_payload(
    name: str,
    payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    if not isinstance(payload, dict):
        msg = f"invalid pub.dev response for {name!r}"
        raise PackageNotFoundError(msg)

    versions_raw = payload.get("versions")
    if not isinstance(versions_raw, list) or not versions_raw:
        msg = f"package not found on pub.dev: {name}"
        raise PackageNotFoundError(msg)

    versions = _pub_versions(versions_raw)
    latest_meta = _latest_pubspec(versions_raw)
    repository = _repository_url(latest_meta)
    homepage = _optional_url(latest_meta.get("homepage"))

    return build_package_info(
        name=name,
        ecosystem="pub",
        versions=versions,
        repository=repository,
        homepage=homepage,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )


def _pub_versions(versions_raw: list[object]) -> list[VersionEntry]:
    versions: list[VersionEntry] = []
    for item in versions_raw:
        if not isinstance(item, dict):
            continue
        version = item.get("version")
        if isinstance(version, str):
            versions.append(VersionEntry(version))
    return versions


def _latest_pubspec(versions_raw: list[object]) -> dict[str, Any]:
    for item in reversed(versions_raw):
        if isinstance(item, dict):
            pubspec = item.get("pubspec")
            if isinstance(pubspec, dict):
                return pubspec
    return {}


def _repository_url(pubspec: dict[str, Any]) -> str | None:
    repository = pubspec.get("repository")
    if isinstance(repository, str):
        return repository.strip() or None
    if isinstance(repository, dict):
        url = repository.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def _optional_url(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
