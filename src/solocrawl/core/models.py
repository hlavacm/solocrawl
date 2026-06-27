"""Shared data types used across the core, MCP shell, and CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """A normalized web search hit from any provider."""

    title: str
    url: str
    snippet: str
    source: str
    score: float = 0.0
    raw: dict[str, Any] | None = None


@dataclass
class FetchResult:
    """The result of fetching and extracting a URL to markdown."""

    url: str
    content: str
    content_type: str
    status: int
    browser_used: bool = False
    title: str | None = None
    author: str | None = None
    date: str | None = None
    language: str | None = None
    site_name: str | None = None


@dataclass
class PackageInfo:
    """Resolved package version information from a registry."""

    name: str
    ecosystem: str
    latest: str
    versions: list[str] = field(default_factory=list)
    repository: str | None = None
    homepage: str | None = None
    changelog: str | None = None
