"""Tests for the optional proxy pool."""

from __future__ import annotations

from solocrawl.config import ProxyConfig, ProxyMode
from solocrawl.core.proxy import (
    ProxyEndpoint,
    ProxyPool,
    ProxyStrategy,
    reset_proxy_pool_for_testing,
)


def setup_function() -> None:
    reset_proxy_pool_for_testing()


def test_proxy_pool_disabled_by_default() -> None:
    pool = ProxyPool(ProxyConfig())
    assert pool.enabled is False
    assert pool.select(domain="example.com") is None


def test_proxy_pool_list_mode_round_robin() -> None:
    config = ProxyConfig(
        enabled=True,
        mode=ProxyMode.LIST,
        proxies=("http://proxy-a:8080", "http://proxy-b:8080"),
    )
    pool = ProxyPool(config, strategy=ProxyStrategy.ROUND_ROBIN)

    first = pool.select()
    second = pool.select()
    third = pool.select()

    assert first is not None and second is not None and third is not None
    assert first.url != second.url
    assert first.url == third.url


def test_proxy_pool_sticky_per_domain() -> None:
    config = ProxyConfig(
        enabled=True,
        mode=ProxyMode.LIST,
        proxies=("http://proxy-a:8080", "http://proxy-b:8080"),
    )
    pool = ProxyPool(config, strategy=ProxyStrategy.STICKY_PER_DOMAIN)

    example = pool.select(domain="example.com")
    example_again = pool.select(domain="example.com")
    other = pool.select(domain="other.com")

    assert example is not None and example_again is not None and other is not None
    assert example.url == example_again.url
    assert example.url != other.url


def test_proxy_pool_marks_unhealthy_and_skips() -> None:
    config = ProxyConfig(
        enabled=True,
        mode=ProxyMode.LIST,
        proxies=("http://proxy-a:8080",),
    )
    pool = ProxyPool(config)
    endpoint = pool.select()
    assert endpoint is not None

    pool.mark_unhealthy(endpoint)
    assert pool.select() is None


def test_proxy_auth_shapes() -> None:
    endpoint = ProxyEndpoint(
        url="http://proxy.example:8080",
        username="user",
        password="pass",
    )

    assert endpoint.httpx_proxy_url() == "http://user:pass@proxy.example:8080"
    playwright = endpoint.playwright_proxy()
    assert playwright["server"] == "http://proxy.example:8080"
    assert playwright["username"] == "user"
    assert playwright["password"] == "pass"
