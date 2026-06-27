"""Optional proxy support for fetch operations."""

from solocrawl.core.proxy.pool import (
    ProxyEndpoint,
    ProxyPool,
    ProxyStrategy,
    get_proxy_pool,
    reset_proxy_pool_for_testing,
)

__all__ = [
    "ProxyEndpoint",
    "ProxyPool",
    "ProxyStrategy",
    "get_proxy_pool",
    "reset_proxy_pool_for_testing",
]
