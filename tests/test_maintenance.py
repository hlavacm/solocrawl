"""Regression checks for the project maintenance audit."""

from dataclasses import replace
from ipaddress import ip_address
from unittest.mock import AsyncMock

import pytest

from solocrawl.config import (
    BrowserConfig,
    ConcurrencyConfig,
    Config,
    FetchConfig,
    ProxyConfig,
    load_config,
)
from solocrawl.core.packages.providers.pypi import _pypi_versions
from solocrawl.core.packages.resolver import (
    InvalidConstraintError,
    parse_semver_constraint,
    resolve_latest,
)
from solocrawl.core.proxy.pool import ProxyPool


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SOLOCRAWL_MAX_CONCURRENCY", "0"),
        ("SOLOCRAWL_PER_DOMAIN_LIMIT", "-1"),
        ("SOLOCRAWL_TIMEOUT_SECONDS", "nan"),
        ("SOLOCRAWL_TIMEOUT_SECONDS", "inf"),
        ("SOLOCRAWL_MAX_RETRIES", "-1"),
        ("SOLOCRAWL_MAX_RESPONSE_BYTES", "0"),
        ("SOLOCRAWL_CACHE_TTL_SECONDS", "-1"),
    ],
)
def test_invalid_config_reports_setting(name: str, value: str) -> None:
    with pytest.raises(ValueError, match=name):
        load_config(env={name: value})


def test_programmatic_config_is_validated() -> None:
    with pytest.raises(ValueError):
        ConcurrencyConfig(max_concurrent_fetches=0)
    with pytest.raises(ValueError):
        FetchConfig(max_response_bytes=0)


def test_enabled_proxy_requires_endpoint() -> None:
    with pytest.raises(ValueError, match="SOLOCRAWL_PROXY"):
        ProxyConfig(enabled=True)


def test_selectors_preserve_explicit_config() -> None:
    from solocrawl.core.discovery import list_search_providers
    from solocrawl.core.packages.selector import select_provider_for_ecosystem
    from solocrawl.core.search.selector import select_providers

    list_search_providers()
    cfg = replace(Config(), concurrency=ConcurrencyConfig(timeout_seconds=1))
    providers = select_providers(cfg, env={})
    assert all(provider._config is cfg for provider in providers)  # type: ignore[attr-defined]
    package = select_provider_for_ecosystem("pypi", cfg, env={})
    assert package is not None
    assert package._config is cfg  # type: ignore[attr-defined]


def test_dead_sticky_proxy_is_replaced() -> None:
    pool = ProxyPool(ProxyConfig(enabled=True, proxies=("http://a:80", "http://b:80")))
    first = pool.select(domain="example.com")
    assert first is not None
    pool.mark_unhealthy(first)
    second = pool.select(domain="example.com")
    assert second is not None
    assert second.url == "http://b:80"


def test_exhausted_proxy_raises() -> None:
    pool = ProxyPool(ProxyConfig(enabled=True, proxies=("http://a:80",)))
    first = pool.select(domain="example.com")
    assert first is not None
    pool.mark_unhealthy(first)
    with pytest.raises(RuntimeError, match="proxy"):
        pool.select(domain="example.com")


@pytest.mark.parametrize("constraint", ["garbage >=1.0", ">=1.0 rubbish", "1 ||", "[1,2)"])
def test_range_rejects_unconsumed_input(constraint: str) -> None:
    with pytest.raises(InvalidConstraintError):
        parse_semver_constraint(constraint)


@pytest.mark.parametrize(
    ("versions", "constraint", "expected"),
    [
        (["1.2.0", "1.3.9", "1.4.0"], "1.2 - 1.3", "1.3.9"),
        (["1.2.3-beta.2", "1.2.3-beta.3"], "^1.2.3-beta.2", "1.2.3-beta.3"),
        (["1.0.0-canary.1", "1.0.0-canary.2"], "^1.0.0-canary.1", "1.0.0-canary.2"),
    ],
)
def test_semver_ranges_preserve_bounds(versions: list[str], constraint: str, expected: str) -> None:
    assert (
        resolve_latest(
            versions,
            constraint=constraint,
            constraint_parser=parse_semver_constraint,
            allow_prerelease=True,
        )
        == expected
    )


def test_pypi_mixed_yanking_keeps_available_release() -> None:
    entries = _pypi_versions(
        {
            "1.0": [{"yanked": True}, {"yanked": False}],
            "2.0": [],
            "3.0": [{"yanked": True}],
        }
    )
    assert resolve_latest(entries) == "1.0"


async def test_redirect_checks_target_robots_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from solocrawl.core.fetch import url_validation
    from solocrawl.core.fetch.client import set_client_for_testing
    from solocrawl.core.fetch.fetcher import fetch
    from solocrawl.core.fetch.robots import RobotsDisallowedError

    # HTTP and DNS both use fixtures; local .test mappings must not affect this test.
    resolve = AsyncMock(return_value=(ip_address("8.8.8.8"),))
    monkeypatch.setattr(url_validation, "_resolve_host_addresses", resolve)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            rules = "User-agent: *\nDisallow: /private" if request.url.host == "target.test" else ""
            return httpx.Response(200, text=rules)
        if request.url.host == "source.test":
            return httpx.Response(302, headers={"Location": "https://target.test/private"})
        pytest.fail("Disallowed redirect target must never be contacted")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await set_client_for_testing(client)
        with pytest.raises(RobotsDisallowedError):
            await fetch(
                "https://source.test/start", config=Config(browser=BrowserConfig(allowed=False))
            )
    assert "https://target.test/robots.txt" in requests
    assert "https://target.test/private" not in requests
    assert {call.args[0] for call in resolve.await_args_list} == {"source.test", "target.test"}


async def test_go_module_case_encoding() -> None:
    import httpx

    from solocrawl.core.fetch.client import set_client_for_testing
    from solocrawl.core.packages.providers.golang import GoModuleProvider

    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, text="v1.0.0" if request.url.path.endswith("/list") else "{}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await set_client_for_testing(client)
        result = await GoModuleProvider(config=Config()).get_package("github.com/Azure/Test")
    assert result.latest == "v1.0.0"
    assert paths == ["/github.com/!azure/!test/@v/list", "/github.com/!azure/!test/@v/v1.0.0.info"]


async def test_swift_follows_tags_pagination() -> None:
    import httpx

    from solocrawl.core.fetch.client import set_client_for_testing
    from solocrawl.core.packages.providers.swift import SwiftProvider

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"name": "2.0.0"}])
        return httpx.Response(
            200,
            json=[{"name": "1.0.0"}],
            headers={
                "Link": (
                    '<https://api.github.com/repos/owner/repo/tags?per_page=100&page=2>; rel="next"'
                ),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await set_client_for_testing(client)
        result = await SwiftProvider(config=Config()).get_package("owner/repo")
    assert result.latest == "2.0.0"


async def test_cache_does_not_cross_fetch_policy() -> None:
    import httpx

    from solocrawl.core.fetch.client import set_client_for_testing
    from solocrawl.core.fetch.fetcher import fetch
    from solocrawl.core.fetch.robots import RobotsDisallowedError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "User-agent: *\nDisallow: /private"
                if request.url.path == "/robots.txt"
                else "cached content " * 50
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await set_client_for_testing(client)
        permissive = Config(fetch=FetchConfig(cache_ttl_seconds=60, respect_robots=False))
        strict = Config(fetch=FetchConfig(cache_ttl_seconds=60, respect_robots=True))
        await fetch("https://example.com/private", config=permissive)
        with pytest.raises(RobotsDisallowedError):
            await fetch("https://example.com/private", config=strict)


def test_proxy_credentials_are_separated_for_browser() -> None:
    from solocrawl.core.proxy import ProxyEndpoint

    endpoint = ProxyEndpoint("http://user:p%40ss@proxy.example:8080")
    assert endpoint.playwright_proxy() == {
        "server": "http://proxy.example:8080",
        "username": "user",
        "password": "p@ss",
    }
    endpoint = ProxyEndpoint("http://proxy.example:8080", username="u@", password="p:")
    assert endpoint.httpx_proxy_url() == "http://u%40:p%3A@proxy.example:8080"


@pytest.mark.parametrize("urls", [("",), (" ",), ("http://",)])
def test_enabled_proxy_rejects_invalid_urls(urls: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="SOLOCRAWL_PROXY"):
        ProxyConfig(enabled=True, proxies=urls)


async def test_proxy_error_does_not_expose_credentials(monkeypatch: pytest.MonkeyPatch) -> None:

    import httpx

    from solocrawl.mcp import server

    monkeypatch.setenv("SOLOCRAWL_PROXY_PASSWORD", "test-password")
    monkeypatch.setattr(
        server,
        "fetch",
        AsyncMock(
            side_effect=httpx.ConnectError(
                "failed http://user:test-password@proxy.example:80 (test-password)"
            )
        ),
    )
    message = await server.scrape("https://example.com")
    assert "test-password" not in message
    assert "user:" not in message


async def test_proxy_exhaustion_never_contacts_direct_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    from solocrawl.core.fetch import fetcher
    from solocrawl.core.fetch.client import set_client_for_testing
    from solocrawl.core.proxy import ProxyUnavailableError, reset_proxy_pool_for_testing

    direct_requests: list[str] = []
    proxy_requests: list[str] = []

    def direct(request: httpx.Request) -> httpx.Response:
        direct_requests.append(str(request.url))
        return httpx.Response(200, text="direct connection must not happen")

    def failing_proxy(request: httpx.Request) -> httpx.Response:
        proxy_requests.append(str(request.url))
        raise httpx.ConnectError("proxy offline", request=request)

    reset_proxy_pool_for_testing()
    direct_client = httpx.AsyncClient(transport=httpx.MockTransport(direct))
    proxy_client = httpx.AsyncClient(transport=httpx.MockTransport(failing_proxy))
    await set_client_for_testing(direct_client)

    def proxy_factory(**kwargs) -> httpx.AsyncClient:
        assert kwargs["proxy"] == "http://proxy.test:80"
        return proxy_client

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", proxy_factory)
    monkeypatch.setattr(fetcher.asyncio, "sleep", AsyncMock())
    config = Config(
        proxy=ProxyConfig(enabled=True, proxies=("http://proxy.test:80",)),
        concurrency=ConcurrencyConfig(max_retries=1),
    )
    with pytest.raises(ProxyUnavailableError):
        await fetcher.fetch("https://example.com/page", config=config)
    assert direct_requests == []
    assert proxy_requests == ["https://example.com/robots.txt", "https://example.com/page"]
    reset_proxy_pool_for_testing()


@pytest.mark.parametrize(
    ("constraint", "next_prerelease"),
    [
        ("^1.2.3", "2.0.0-alpha"),
        ("~1.2.3", "1.3.0-alpha"),
        ("1.2.x", "1.3.0-alpha"),
        ("1.2", "1.3.0-alpha"),
        ("1.2 - 1.2", "1.3.0-alpha"),
    ],
)
def test_derived_semver_bound_excludes_next_release_prereleases(
    constraint: str, next_prerelease: str
) -> None:
    assert (
        resolve_latest(
            ["1.2.9", next_prerelease],
            constraint=constraint,
            constraint_parser=parse_semver_constraint,
            allow_prerelease=True,
        )
        == "1.2.9"
    )


@pytest.mark.parametrize(
    ("constraint", "expected"),
    [
        (">1", "2.0.0"),
        ("<=1", "1.9.9"),
        ("=1.2", "1.2.9"),
        ("<1.2", "1.0.0"),
    ],
)
def test_partial_comparator_expansion(constraint: str, expected: str) -> None:
    assert (
        resolve_latest(
            ["1.0.0", "1.2.0", "1.2.9", "1.9.9", "2.0.0"],
            constraint=constraint,
            constraint_parser=parse_semver_constraint,
        )
        == expected
    )


@pytest.mark.parametrize("ecosystem", ["maven", "nuget", "rubygems"])
@pytest.mark.parametrize("constraint", [None, ">=1,<2"])
def test_native_numeric_versions_keep_four_components(
    ecosystem: str, constraint: str | None
) -> None:
    from solocrawl.core.packages.providers.base import build_package_info
    from solocrawl.core.packages.resolver import VersionEntry

    info = build_package_info(
        name="example",
        ecosystem=ecosystem,
        versions=[VersionEntry("1.2.3"), VersionEntry("1.2.3.4")],
        constraint=constraint,
        constraint_parser=parse_semver_constraint,
    )
    assert info.latest == "1.2.3.4"
    assert info.versions == ["1.2.3"]
