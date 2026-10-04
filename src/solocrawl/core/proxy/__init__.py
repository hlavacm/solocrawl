"""Optional proxy support for fetch operations."""

from solocrawl.core.proxy.pool import (
    ProxyEndpoint,
    ProxyPool,
    ProxyStrategy,
    ProxyUnavailableError,
    get_proxy_pool,
    redact_proxy_credentials,
    reset_proxy_pool_for_testing,
)

__all__ = [
    "ProxyEndpoint",
    "ProxyPool",
    "ProxyStrategy",
    "ProxyUnavailableError",
    "get_proxy_pool",
    "redact_proxy_credentials",
    "reset_proxy_pool_for_testing",
]
