"""Discovery of registered search and package providers.

Importing this module imports the provider packages, which is what triggers their
import-time ``@register`` decorators. Both shells (CLI ``providers`` command and the
MCP ``list_providers`` tool) read from here so the listing logic lives in one place.
"""

from __future__ import annotations

from dataclasses import dataclass

from solocrawl.core.packages import providers as _package_providers  # noqa: F401
from solocrawl.core.packages.registry import (
    list_registrations as _list_package_registrations,
)
from solocrawl.core.search import providers as _search_providers  # noqa: F401
from solocrawl.core.search.registry import (
    list_registrations as _list_search_registrations,
)


@dataclass(frozen=True)
class ProviderSummary:
    """Normalized description of a registered provider for both subsystems."""

    kind: str  # "search" or "package"
    name: str
    zero_config: bool
    required_env_key: str | None
    ecosystem: str | None = None


def list_search_providers() -> list[ProviderSummary]:
    """Return summaries for all registered search providers."""
    return [
        ProviderSummary(
            kind="search",
            name=reg.name,
            zero_config=reg.zero_config,
            required_env_key=reg.required_env_key,
        )
        for reg in _list_search_registrations()
    ]


def list_package_providers() -> list[ProviderSummary]:
    """Return summaries for all registered package providers."""
    return [
        ProviderSummary(
            kind="package",
            name=reg.name,
            zero_config=reg.zero_config,
            required_env_key=reg.required_env_key,
            ecosystem=reg.ecosystem,
        )
        for reg in _list_package_registrations()
    ]


def provider_label(summary: ProviderSummary) -> str:
    """Return the display label for a provider (includes ecosystem when distinct)."""
    if summary.ecosystem is not None and summary.ecosystem != summary.name:
        return f"{summary.name} ({summary.ecosystem})"
    return summary.name


def provider_status_note(summary: ProviderSummary) -> tuple[str, str]:
    """Return ``(status, note)`` for text listings (``note`` may be empty)."""
    status = "default" if summary.zero_config else "opt-in"
    note = f" (requires {summary.required_env_key})" if summary.required_env_key else ""
    return status, note


__all__ = [
    "ProviderSummary",
    "list_package_providers",
    "list_search_providers",
    "provider_label",
    "provider_status_note",
]
