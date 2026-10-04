"""Configuration loaded from environment variables with sensible defaults."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse

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

    def __post_init__(self) -> None:
        _positive("SOLOCRAWL_MAX_CONCURRENCY", self.max_concurrent_fetches)
        _positive("SOLOCRAWL_PER_DOMAIN_LIMIT", self.per_domain_limit)
        _positive("SOLOCRAWL_TIMEOUT_SECONDS", self.timeout_seconds)
        _positive("SOLOCRAWL_MAX_RETRIES", self.max_retries, zero_allowed=True)


@dataclass(frozen=True)
class ProxyConfig:
    """Optional proxy settings (disabled by default)."""

    enabled: bool = False
    mode: ProxyMode = ProxyMode.LIST
    proxies: tuple[str, ...] = ()
    endpoint: str | None = None
    username: str | None = None
    password: str | None = None

    def __post_init__(self) -> None:
        if not self.enabled:
            return
        urls = (self.endpoint,) if self.mode is ProxyMode.ENDPOINT else self.proxies
        if not urls:
            raise ValueError("SOLOCRAWL_PROXY_ENABLED requires a proxy list or endpoint")
        for url in urls:
            try:
                parsed = urlparse(url or "")
                valid = (
                    bool(url and url.strip())
                    and parsed.scheme in {"http", "https"}
                    and parsed.hostname is not None
                    and (parsed.port is None or parsed.port > 0)
                )
            except ValueError:
                valid = False
            if not valid:
                raise ValueError(
                    "SOLOCRAWL_PROXY_LIST / ENDPOINT requires valid HTTP(S) proxy URLs"
                )


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

    def __post_init__(self) -> None:
        _positive("SOLOCRAWL_MAX_RESPONSE_BYTES", self.max_response_bytes)
        _positive("SOLOCRAWL_CACHE_TTL_SECONDS", self.cache_ttl_seconds, zero_allowed=True)


@dataclass(frozen=True)
class Config:
    """Top-level SoloCrawl configuration."""

    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    fetch: FetchConfig = field(default_factory=FetchConfig)
    enabled_providers: frozenset[str] = frozenset()


def _positive(name: str, value: float, *, zero_allowed: bool = False) -> None:
    if not math.isfinite(value) or (value < 0 if zero_allowed else value <= 0):
        bound = "non-negative" if zero_allowed else "positive"
        raise ValueError(f"{name} must be finite and {bound}")


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
        try:
            return _parse_bool(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be a boolean") from exc

    def get_int(name: str, default: int) -> int:
        raw = get(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc

    def get_float(name: str, default: float) -> float:
        raw = get(name)
        if raw is None:
            return default
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be a number") from exc

    def get_csv(name: str) -> tuple[str, ...]:
        raw = get(name)
        if raw is None:
            return ()
        return tuple(item.strip() for item in raw.split(",") if item.strip())

    proxy_mode_raw = get("SOLOCRAWL_PROXY_MODE")
    try:
        proxy_mode = ProxyMode(proxy_mode_raw.lower()) if proxy_mode_raw else ProxyMode.LIST
    except ValueError as exc:
        raise ValueError("SOLOCRAWL_PROXY_MODE must be list or endpoint") from exc

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
