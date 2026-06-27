"""Maven Central package provider."""

from __future__ import annotations

import logging

# Stdlib ElementTree is used deliberately: it does not resolve external entities,
# so registry XML cannot trigger XXE. (defusedxml would add a dependency for no gain.)
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.fetch.client import get_client
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.providers.base import PackageNotFoundError, build_package_info
from solocrawl.core.packages.registry import register
from solocrawl.core.packages.resolver import VersionEntry, parse_semver_constraint

logger = logging.getLogger(__name__)


@register("maven", ecosystem="maven", zero_config=True)
class MavenProvider:
    """Fetch package metadata from Maven Central."""

    name = "maven"
    ecosystem = "maven"
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
        """Return package metadata for a Maven artifact."""
        package_name = name.strip()
        if ":" not in package_name:
            msg = "maven package names must use groupId:artifactId format"
            raise PackageNotFoundError(msg)

        group_id, artifact_id = package_name.split(":", maxsplit=1)
        group_id = group_id.strip()
        artifact_id = artifact_id.strip()
        if not group_id or not artifact_id:
            msg = "maven package names must use groupId:artifactId format"
            raise PackageNotFoundError(msg)

        group_path = "/".join(quote(part, safe="") for part in group_id.split("."))
        url = (
            f"https://repo1.maven.org/maven2/"
            f"{group_path}/{quote(artifact_id, safe='')}/maven-metadata.xml"
        )

        try:
            client = await get_client(
                self._config.concurrency,
                user_agent=self._config.fetch.user_agent,
            )
            response = await client.get(url)
            if response.status_code == 404:
                msg = f"package not found on Maven Central: {package_name}"
                raise PackageNotFoundError(msg)
            response.raise_for_status()
            metadata_xml = response.text
        except httpx.HTTPError as exc:
            logger.warning("maven lookup failed for %r: %s", package_name, exc)
            msg = f"failed to fetch package from Maven Central: {package_name}"
            raise PackageNotFoundError(msg) from exc

        return _parse_maven_metadata(
            package_name,
            metadata_xml,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )


def _parse_maven_metadata(
    name: str,
    metadata_xml: str,
    *,
    constraint: str | None,
    allow_prerelease: bool,
) -> PackageInfo:
    try:
        root = ET.fromstring(metadata_xml)
    except ET.ParseError as exc:
        msg = f"invalid Maven metadata for {name!r}"
        raise PackageNotFoundError(msg) from exc

    versions_node = root.find("./versioning/versions")
    if versions_node is None:
        msg = f"package not found on Maven Central: {name}"
        raise PackageNotFoundError(msg)

    versions = [
        VersionEntry(version.text) for version in versions_node.findall("version") if version.text
    ]
    if not versions:
        msg = f"package not found on Maven Central: {name}"
        raise PackageNotFoundError(msg)

    return build_package_info(
        name=name,
        ecosystem="maven",
        versions=versions,
        constraint=constraint,
        allow_prerelease=allow_prerelease,
        constraint_parser=parse_semver_constraint,
    )
