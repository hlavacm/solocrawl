"""Proxy endpoint representation and selection."""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote, unquote, urlparse

from solocrawl.config import ProxyConfig, ProxyMode


class ProxyUnavailableError(RuntimeError):
    """Raised when an enabled proxy pool has no healthy endpoint."""


class ProxyStrategy(StrEnum):
    """How proxies are selected from a pool."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    STICKY_PER_DOMAIN = "sticky_per_domain"


@dataclass(frozen=True)
class ProxyEndpoint:
    """A proxy endpoint with optional credentials."""

    url: str
    username: str | None = None
    password: str | None = None
    healthy: bool = True

    def httpx_proxy_url(self) -> str:
        """Return a proxy URL suitable for httpx."""
        parsed = urlparse(self.url)
        if self.username is not None:
            host = parsed.netloc.rsplit("@", 1)[-1]
            credentials = quote(self.username, safe="")
            if self.password is not None:
                credentials += ":" + quote(self.password, safe="")
            return parsed._replace(netloc=f"{credentials}@{host}").geturl()
        return self.url

    def playwright_proxy(self) -> dict[str, str]:
        """Return Playwright settings with credentials outside the server URL."""
        parsed = urlparse(self.url)
        settings = {"server": parsed._replace(netloc=parsed.netloc.rsplit("@", 1)[-1]).geturl()}
        username = self.username if self.username is not None else parsed.username
        password = self.password if self.password is not None else parsed.password
        if username is not None:
            settings["username"] = username if self.username is not None else unquote(username)
        if password is not None:
            settings["password"] = password if self.password is not None else unquote(password)
        return settings


class ProxyPool:
    """Optional proxy pool with rotation and health tracking."""

    def __init__(
        self,
        config: ProxyConfig,
        *,
        strategy: ProxyStrategy = ProxyStrategy.STICKY_PER_DOMAIN,
    ) -> None:
        self._config = config
        self._strategy = strategy
        self._index = 0
        self._sticky: dict[str, ProxyEndpoint] = {}
        self._endpoints = self._build_endpoints(config)

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._endpoints)

    def _build_endpoints(self, config: ProxyConfig) -> list[ProxyEndpoint]:
        if not config.enabled:
            return []

        if config.mode is ProxyMode.ENDPOINT and config.endpoint:
            return [
                ProxyEndpoint(
                    url=config.endpoint,
                    username=config.username,
                    password=config.password,
                )
            ]

        return [
            ProxyEndpoint(
                url=proxy,
                username=config.username,
                password=config.password,
            )
            for proxy in config.proxies
        ]

    def healthy_endpoints(self) -> list[ProxyEndpoint]:
        return [endpoint for endpoint in self._endpoints if endpoint.healthy]

    def mark_unhealthy(self, endpoint: ProxyEndpoint) -> None:
        for index, current in enumerate(self._endpoints):
            if current.url == endpoint.url:
                self._endpoints[index] = ProxyEndpoint(
                    url=current.url,
                    username=current.username,
                    password=current.password,
                    healthy=False,
                )
                self._sticky = {
                    key: value for key, value in self._sticky.items() if value.url != endpoint.url
                }
                break

    def select(self, *, domain: str | None = None) -> ProxyEndpoint | None:
        """Select a proxy endpoint for a request."""
        if not self.enabled:
            return None

        candidates = self.healthy_endpoints()
        if not candidates:
            raise ProxyUnavailableError("no healthy proxy endpoint available")

        if self._config.mode is ProxyMode.ENDPOINT:
            return candidates[0]

        if self._strategy is ProxyStrategy.STICKY_PER_DOMAIN and domain:
            sticky = self._sticky.get(domain)
            if sticky is not None and sticky.healthy:
                return sticky
            chosen = candidates[self._index % len(candidates)]
            self._index += 1
            self._sticky[domain] = chosen
            return chosen

        if self._strategy is ProxyStrategy.RANDOM:
            return random.choice(candidates)

        chosen = candidates[self._index % len(candidates)]
        self._index += 1
        return chosen


_POOL: ProxyPool | None = None


def get_proxy_pool(config: ProxyConfig) -> ProxyPool:
    """Return the process-wide proxy pool for a configuration."""
    global _POOL
    if _POOL is None or _POOL._config != config:
        _POOL = ProxyPool(config)
    return _POOL


def reset_proxy_pool_for_testing() -> None:
    """Clear the cached proxy pool (tests only)."""
    global _POOL
    _POOL = None


def redact_proxy_credentials(message: str, config: ProxyConfig | None = None) -> str:
    """Remove proxy URL credentials and known passwords from an error message."""
    message = re.sub(r"(\b[a-zA-Z][\w+.-]*://)[^\s/@]+@", r"\1[redacted]@", message)
    password = config.password if config is not None else os.environ.get("SOLOCRAWL_PROXY_PASSWORD")
    return message.replace(password, "[redacted]") if password else message
