"""Package provider protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from solocrawl.core.models import PackageInfo


@runtime_checkable
class PackageProvider(Protocol):
    """Protocol for live package version lookup providers."""

    name: str
    ecosystem: str
    zero_config: bool

    async def get_package(
        self,
        name: str,
        *,
        constraint: str | None = None,
        allow_prerelease: bool = False,
    ) -> PackageInfo:
        """Fetch package metadata and versions from a registry."""
        ...
