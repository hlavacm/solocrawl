"""npm package provider."""

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


@register("npm", ecosystem="npm", zero_config=True)
class NpmProvider:
    """Fetch package metadata from the npm registry."""

    name = "npm"
    ecosystem = "npm"
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
        """Return package metadata for an npm package."""
        package_name = name.strip()
        if not package_name:
            msg = "package name must not be empty"
            raise PackageNotFoundError(msg)

        url = f"https://registry.npmjs.org/{quote(package_name, safe='@/')}"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url)
            if response.status_code == 404:
                msg = f"package not found on npm: {package_name}"
                raise PackageNotFoundError(msg)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("npm lookup failed for %r: %s", package_name, exc)
            msg = f"failed to fetch package from npm: {package_name}"
            raise PackageNotFoundError(msg) from exc

        return _parse_npm_payload(
            package_name,
            payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_npm_payload(
    name: str,
    payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    if not isinstance(payload, dict):
        msg = f"invalid npm response for {name!r}"
        raise PackageNotFoundError(msg)

    versions_obj = payload.get("versions")
    if not isinstance(versions_obj, dict) or not versions_obj:
        msg = f"package not found on npm: {name}"
        raise PackageNotFoundError(msg)

    versions = [VersionEntry(version) for version in versions_obj]
    latest_meta = _latest_metadata(payload, versions_obj)
    repository = _repository_url(latest_meta)
    homepage = latest_meta.get("homepage") if isinstance(latest_meta, dict) else None
    homepage = homepage if isinstance(homepage, str) else None

    return build_package_info(
        name=name,
        ecosystem="npm",
        versions=versions,
        repository=repository,
        homepage=homepage,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )


def _latest_metadata(payload: dict[str, Any], versions_obj: dict[str, Any]) -> dict[str, Any]:
    dist_tags = payload.get("dist-tags")
    if isinstance(dist_tags, dict):
        latest = dist_tags.get("latest")
        if isinstance(latest, str):
            meta = versions_obj.get(latest)
            if isinstance(meta, dict):
                return meta
    first_key = next(iter(versions_obj))
    meta = versions_obj.get(first_key)
    return meta if isinstance(meta, dict) else {}


def _repository_url(metadata: dict[str, Any]) -> str | None:
    repository = metadata.get("repository")
    if isinstance(repository, dict):
        url = repository.get("url")
        if isinstance(url, str):
            return url.removeprefix("git+").removesuffix(".git")
    if isinstance(repository, str):
        return repository.removeprefix("git+").removesuffix(".git")
    return None
