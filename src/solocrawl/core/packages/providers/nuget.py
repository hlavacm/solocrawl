"""NuGet package provider."""

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


@register("nuget", ecosystem="nuget", zero_config=True)
class NuGetProvider:
    """Fetch package metadata from NuGet.org."""

    name = "nuget"
    ecosystem = "nuget"
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
        """Return package metadata for a NuGet package."""
        package_name = name.strip()
        if not package_name:
            msg = "package name must not be empty"
            raise PackageNotFoundError(msg)

        package_id = quote(package_name.lower(), safe="")
        index_url = f"https://api.nuget.org/v3-flatcontainer/{package_id}/index.json"
        registration_url = (
            f"https://api.nuget.org/v3/registration5-gz-semver2/{package_id}/index.json"
        )

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            index_response = await client.get(index_url)
            if index_response.status_code == 404:
                msg = f"package not found on NuGet: {package_name}"
                raise PackageNotFoundError(msg)
            index_response.raise_for_status()

            registration_response = await client.get(registration_url)
            registration_payload: object = {}
            if registration_response.status_code == 200:
                registration_payload = registration_response.json()
                registration_payload = await _load_registration_pages(
                    client,
                    registration_payload,
                )
            index_payload = index_response.json()
        except httpx.HTTPError as exc:
            logger.warning("nuget lookup failed for %r: %s", package_name, exc)
            msg = f"failed to fetch package from NuGet: {package_name}"
            raise PackageNotFoundError(msg) from exc

        return _parse_nuget_payload(
            package_name,
            index_payload,
            registration_payload,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


async def _load_registration_pages(
    client: httpx.AsyncClient,
    registration_payload: object,
) -> object:
    if not isinstance(registration_payload, dict):
        return registration_payload

    pages = registration_payload.get("items")
    if not isinstance(pages, list):
        return registration_payload

    loaded_pages: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        page_items = page.get("items")
        if isinstance(page_items, list):
            loaded_pages.append(page)
            continue

        page_url = page.get("@id")
        if not isinstance(page_url, str):
            loaded_pages.append(page)
            continue

        response = await client.get(page_url)
        if response.status_code != 200:
            loaded_pages.append(page)
            continue
        page_payload = response.json()
        if isinstance(page_payload, dict):
            loaded_pages.append(page_payload)
        else:
            loaded_pages.append(page)

    return {**registration_payload, "items": loaded_pages}


def _parse_nuget_payload(
    name: str,
    index_payload: object,
    registration_payload: object,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    if not isinstance(index_payload, dict):
        msg = f"invalid NuGet response for {name!r}"
        raise PackageNotFoundError(msg)

    versions_raw = index_payload.get("versions")
    if not isinstance(versions_raw, list) or not versions_raw:
        msg = f"package not found on NuGet: {name}"
        raise PackageNotFoundError(msg)

    listed_versions = _listed_versions(registration_payload)
    versions = [
        VersionEntry(
            version,
            yanked=listed_versions.get(version) is False,
        )
        for version in versions_raw
        if isinstance(version, str)
    ]
    metadata = _registration_metadata(registration_payload)

    return build_package_info(
        name=name,
        ecosystem="nuget",
        versions=versions,
        repository=metadata.get("projectUrl"),
        homepage=metadata.get("projectUrl"),
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )


def _listed_versions(registration_payload: object) -> dict[str, bool]:
    listed: dict[str, bool] = {}
    for item in _registration_items(registration_payload):
        catalog = item.get("catalogEntry")
        if not isinstance(catalog, dict):
            continue
        version = catalog.get("version")
        if not isinstance(version, str):
            continue
        listed[version] = catalog.get("listed", True) is not False
    return listed


def _registration_metadata(registration_payload: object) -> dict[str, str | None]:
    project_url: str | None = None
    for item in reversed(_registration_items(registration_payload)):
        catalog = item.get("catalogEntry")
        if not isinstance(catalog, dict):
            continue
        if catalog.get("listed") is False:
            continue
        url = catalog.get("projectUrl")
        if isinstance(url, str) and url.strip():
            project_url = url.strip()
            break
    return {"projectUrl": project_url}


def _registration_items(registration_payload: object) -> list[dict[str, Any]]:
    if not isinstance(registration_payload, dict):
        return []

    items: list[dict[str, Any]] = []
    for page in registration_payload.get("items", []):
        if not isinstance(page, dict):
            continue
        page_items = page.get("items")
        if isinstance(page_items, list):
            items.extend(item for item in page_items if isinstance(item, dict))
    return items
