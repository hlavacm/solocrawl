"""crates.io package provider."""

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


@register("crates", ecosystem="crates", zero_config=True, configurable=True)
class CratesProvider:
    """Fetch package metadata from crates.io."""

    name = "crates"
    ecosystem = "crates"
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
        """Return package metadata for a Rust crate."""
        package_name = name.strip()
        if not package_name:
            msg = "package name must not be empty"
            raise PackageNotFoundError(msg)

        url = f"https://crates.io/api/v1/crates/{quote(package_name, safe='')}"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url)
            if response.status_code == 404:
                msg = f"package not found on crates.io: {package_name}"
                raise PackageNotFoundError(msg)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("crates.io lookup failed for %r: %s", package_name, exc)
            msg = f"failed to fetch package from crates.io: {package_name}"
            raise PackageNotFoundError(msg) from exc

        return _parse_crates_payload(
            package_name,
            payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_crates_payload(
    name: str,
    payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    if not isinstance(payload, dict):
        msg = f"invalid crates.io response for {name!r}"
        raise PackageNotFoundError(msg)

    versions_raw = payload.get("versions")
    if not isinstance(versions_raw, list) or not versions_raw:
        msg = f"package not found on crates.io: {name}"
        raise PackageNotFoundError(msg)

    versions = _crates_versions(versions_raw)
    latest_meta = _latest_metadata(versions_raw)
    repository = _optional_url(latest_meta.get("repository"))
    homepage = _optional_url(latest_meta.get("homepage"))

    return build_package_info(
        name=name,
        ecosystem="crates",
        versions=versions,
        repository=repository,
        homepage=homepage,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )


def _crates_versions(versions_raw: list[object]) -> list[VersionEntry]:
    versions: list[VersionEntry] = []
    for item in versions_raw:
        if not isinstance(item, dict):
            continue
        num = item.get("num")
        if not isinstance(num, str):
            continue
        yanked = item.get("yanked") is True
        versions.append(VersionEntry(num, yanked=yanked))
    return versions


def _latest_metadata(versions_raw: list[object]) -> dict[str, Any]:
    for item in versions_raw:
        if isinstance(item, dict) and item.get("yanked") is not True:
            return item
    first = versions_raw[0]
    return first if isinstance(first, dict) else {}


def _optional_url(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
