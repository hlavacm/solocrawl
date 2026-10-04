"""Go module proxy package provider."""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.providers.base import PackageNotFoundError, build_package_info
from solocrawl.core.packages.registry import register
from solocrawl.core.packages.resolver import (
    VersionEntry,
    normalize_go_module_version,
    parse_semver_constraint,
    resolve_latest,
)

logger = logging.getLogger(__name__)


@register("go", ecosystem="go", zero_config=True, configurable=True)
class GoModuleProvider:
    """Fetch module versions from proxy.golang.org."""

    name = "go"
    ecosystem = "go"
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
        """Return package metadata for a Go module."""
        module_path = name.strip()
        if not module_path:
            msg = "module path must not be empty"
            raise PackageNotFoundError(msg)

        escaped_path = quote(
            "".join(
                "!" + char.lower() if char.isascii() and char.isupper() else char
                for char in module_path
            ),
            safe="/!",
        )
        list_url = f"https://proxy.golang.org/{escaped_path}/@v/list"

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(list_url)
            if response.status_code == 404 or not response.text.strip():
                msg = f"module not found on proxy.golang.org: {module_path}"
                raise PackageNotFoundError(msg)
            response.raise_for_status()
            versions = _parse_go_version_list(response.text)
            info_payload: object = {}
            latest = resolve_latest(
                versions,
                constraint=constraint,
                allow_prerelease=allow_prerelease,
                constraint_parser=parse_semver_constraint,
                version_normalizer=normalize_go_module_version,
            )
            if latest is None:
                msg = f"no matching version found for {module_path!r}"
                raise PackageNotFoundError(msg)

            info_response = await client.get(
                f"https://proxy.golang.org/{escaped_path}/@v/{quote(latest, safe='')}.info"
            )
            if info_response.status_code == 200:
                info_payload = info_response.json()
        except httpx.HTTPError as exc:
            logger.warning("go module lookup failed for %r: %s", module_path, exc)
            msg = f"failed to fetch module from proxy.golang.org: {module_path}"
            raise PackageNotFoundError(msg) from exc

        return _parse_go_module_payload(
            module_path,
            versions,
            info_payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_go_module_payload(
    module_path: str,
    versions: list[VersionEntry],
    info_payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    repository = _repository_from_info(info_payload)
    return build_package_info(
        name=module_path,
        ecosystem="go",
        versions=versions,
        repository=repository,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
        version_normalizer=normalize_go_module_version,
    )


def _parse_go_version_list(body: str) -> list[VersionEntry]:
    versions: list[VersionEntry] = []
    for line in body.splitlines():
        version = line.strip()
        if version:
            versions.append(VersionEntry(version))
    return versions


def _repository_from_info(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    origin = payload.get("Origin")
    if not isinstance(origin, dict):
        return None
    url = origin.get("URL")
    return url.strip() if isinstance(url, str) and url.strip() else None
