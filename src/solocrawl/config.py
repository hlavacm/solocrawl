"""Configuration loaded from environment variables with sensible defaults."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from dotenv import load_dotenv


def init_env() -> None:
    """Load variables from a ``.env`` file into ``os.environ`` when present.

    Existing environment variables are not overridden. Safe to call repeatedly.
    """
    load_dotenv()


class ProxyMode(StrEnum):
    """How proxy endpoints are supplied."""

    LIST = "list"
    ENDPOINT = "endpoint"


@dataclass(frozen=True)
class ConcurrencyConfig:
    """Limits for concurrent network operations."""

    max_concurrent_fetches: int = 10
    per_domain_limit: int = 2
    timeout_seconds: float = 30.0
    max_retries: int = 3


@dataclass(frozen=True)
class ProxyConfig:
    """Optional proxy settings (disabled by default)."""

    enabled: bool = False
    mode: ProxyMode = ProxyMode.LIST
    proxies: tuple[str, ...] = ()
    endpoint: str | None = None
    username: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class BrowserConfig:
    """Playwright browser fallback settings."""

    allowed: bool = True


@dataclass(frozen=True)
class FetchConfig:
    """Fetch/scrape policy settings."""

    allow_internal_urls: bool = False
    user_agent: str | None = None
    max_response_bytes: int = 10 * 1024 * 1024
    respect_robots: bool = True
    cache_ttl_seconds: int = 0


@dataclass(frozen=True)
class Config:
    """Top-level SoloCrawl configuration."""

    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    fetch: FetchConfig = field(default_factory=FetchConfig)
    enabled_providers: frozenset[str] = frozenset()


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    msg = f"invalid boolean value: {value!r}"
    raise ValueError(msg)


def load_config(*, env: Mapping[str, str] | None = None) -> Config:
    """Load configuration from environment variables.

    Uses the ``SOLOCRAWL_`` prefix. When ``env`` is omitted, a ``.env`` file in the
    project tree (if present) is loaded first, then ``os.environ`` is used.
    """
    if env is None:
        init_env()
    source = os.environ if env is None else env

    def get(name: str) -> str | None:
        value = source.get(name)
        if value is None or value.strip() == "":
            return None
        return value.strip()

    def get_bool(name: str, default: bool) -> bool:
        raw = get(name)
        if raw is None:
            return default
        return _parse_bool(raw)

    def get_int(name: str, default: int) -> int:
        raw = get(name)
        if raw is None:
            return default
        return int(raw)

    def get_float(name: str, default: float) -> float:
        raw = get(name)
        if raw is None:
            return default
        return float(raw)

    def get_csv(name: str) -> tuple[str, ...]:
        raw = get(name)
        if raw is None:
            return ()
        return tuple(item.strip() for item in raw.split(",") if item.strip())

    proxy_mode_raw = get("SOLOCRAWL_PROXY_MODE")
    proxy_mode = ProxyMode(proxy_mode_raw.lower()) if proxy_mode_raw else ProxyMode.LIST

    return Config(
        concurrency=ConcurrencyConfig(
            max_concurrent_fetches=get_int("SOLOCRAWL_MAX_CONCURRENCY", 10),
            per_domain_limit=get_int("SOLOCRAWL_PER_DOMAIN_LIMIT", 2),
            timeout_seconds=get_float("SOLOCRAWL_TIMEOUT_SECONDS", 30.0),
            max_retries=get_int("SOLOCRAWL_MAX_RETRIES", 3),
        ),
        proxy=ProxyConfig(
            enabled=get_bool("SOLOCRAWL_PROXY_ENABLED", False),
            mode=proxy_mode,
            proxies=tuple(get_csv("SOLOCRAWL_PROXY_LIST")),
            endpoint=get("SOLOCRAWL_PROXY_ENDPOINT"),
            username=get("SOLOCRAWL_PROXY_USERNAME"),
            password=get("SOLOCRAWL_PROXY_PASSWORD"),
        ),
        browser=BrowserConfig(
            allowed=get_bool("SOLOCRAWL_BROWSER_ALLOWED", True),
        ),
        fetch=FetchConfig(
            allow_internal_urls=get_bool("SOLOCRAWL_ALLOW_INTERNAL_URLS", False),
            user_agent=get("SOLOCRAWL_USER_AGENT"),
            max_response_bytes=get_int("SOLOCRAWL_MAX_RESPONSE_BYTES", 10 * 1024 * 1024),
            respect_robots=get_bool("SOLOCRAWL_RESPECT_ROBOTS", True),
            cache_ttl_seconds=get_int("SOLOCRAWL_CACHE_TTL_SECONDS", 0),
        ),
        enabled_providers=frozenset(get_csv("SOLOCRAWL_ENABLE_PROVIDERS")),
    )
