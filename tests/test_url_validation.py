"""Tests for fetch URL validation."""

from __future__ import annotations

import ipaddress

import httpx
import pytest

from solocrawl.core.fetch.client import (
    default_user_agent,
    set_client_for_testing,
)
from solocrawl.core.fetch.fetcher import fetch
from solocrawl.core.fetch.url_validation import (
    FetchUrlError,
    ensure_fetch_url_allowed,
    ensure_fetch_url_resolves_allowed,
    validate_fetch_url,
)


def test_validate_fetch_url_accepts_public_https() -> None:
    assert validate_fetch_url("https://example.com/page") is None


def test_validate_fetch_url_rejects_non_http_scheme() -> None:
    assert validate_fetch_url("ftp://example.com") == "URL must use http or https"


def test_validate_fetch_url_rejects_missing_host() -> None:
    assert validate_fetch_url("https:///path") == "URL must include a host"


def test_validate_fetch_url_blocks_localhost() -> None:
    error = validate_fetch_url("http://127.0.0.1:8080/admin")
    assert error is not None
    assert "127.0.0.1" in error


def test_validate_fetch_url_blocks_metadata_endpoint() -> None:
    error = validate_fetch_url("http://169.254.169.254/latest/meta-data/")
    assert error is not None
    assert "169.254.169.254" in error


def test_validate_fetch_url_allows_internal_when_configured() -> None:
    assert validate_fetch_url("http://127.0.0.1:8080", allow_internal=True) is None


def test_fetch_rejects_internal_url_by_default() -> None:
    with pytest.raises(FetchUrlError):
        ensure_fetch_url_allowed("http://localhost/admin")


async def test_fetch_rejects_hostname_that_resolves_internal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def resolve(host: str, port: int | None):
        assert host == "public.example"
        assert port is None
        return (ipaddress.ip_address("127.0.0.1"),)

    monkeypatch.setattr(
        "solocrawl.core.fetch.url_validation._resolve_host_addresses",
        resolve,
    )

    with pytest.raises(FetchUrlError, match="public.example"):
        await ensure_fetch_url_resolves_allowed("https://public.example/page")


async def test_fetch_allows_internal_dns_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def resolve(host: str, port: int | None):
        return (ipaddress.ip_address("127.0.0.1"),)

    monkeypatch.setattr(
        "solocrawl.core.fetch.url_validation._resolve_host_addresses",
        resolve,
    )

    await ensure_fetch_url_resolves_allowed(
        "https://public.example/page",
        allow_internal=True,
    )


async def test_fetch_blocks_redirect_to_internal_host(article_html: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(
                302,
                headers={"Location": "http://127.0.0.1/secret"},
                request=request,
            )
        return httpx.Response(200, text=article_html, request=request)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    )
    await set_client_for_testing(client)

    with pytest.raises(FetchUrlError):
        await fetch("https://example.com/redirect")

    await client.aclose()


async def test_fetch_blocks_redirect_to_hostname_that_resolves_internal(
    article_html: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def resolve(host: str, port: int | None):
        if host == "internal.example":
            return (ipaddress.ip_address("10.0.0.5"),)
        return (ipaddress.ip_address("8.8.8.8"),)

    monkeypatch.setattr(
        "solocrawl.core.fetch.url_validation._resolve_host_addresses",
        resolve,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(
                302,
                headers={"Location": "https://internal.example/secret"},
                request=request,
            )
        return httpx.Response(200, text=article_html, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    with pytest.raises(FetchUrlError, match="internal.example"):
        await fetch("https://example.com/redirect")

    await client.aclose()


async def test_get_client_applies_user_agent() -> None:
    from solocrawl.config import ConcurrencyConfig
    from solocrawl.core.fetch.client import close_client, get_client

    await set_client_for_testing(None)
    client = await get_client(
        ConcurrencyConfig(),
        user_agent="SoloCrawl-Test/1.0",
    )

    assert client.headers.get("User-Agent") == "SoloCrawl-Test/1.0"
    await close_client()


def test_default_user_agent_contains_version() -> None:
    assert "SoloCrawl/" in default_user_agent()
