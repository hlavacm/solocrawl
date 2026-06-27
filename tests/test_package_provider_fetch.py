"""Provider-level (network path) tests for package providers via MockTransport."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages.protocol import PackageProvider
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.providers.crates import CratesProvider
from solocrawl.core.packages.providers.golang import GoModuleProvider
from solocrawl.core.packages.providers.maven import MavenProvider
from solocrawl.core.packages.providers.npm import NpmProvider
from solocrawl.core.packages.providers.nuget import NuGetProvider
from solocrawl.core.packages.providers.packagist import PackagistProvider
from solocrawl.core.packages.providers.pub import PubProvider
from solocrawl.core.packages.providers.rubygems import RubyGemsProvider

Route = tuple[str, str, str]  # (url substring, fixture name, "json" | "text")


def _router(read_fixture, routes: list[Route]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for needle, fixture, kind in routes:
            if needle in url:
                body = read_fixture(fixture)
                if kind == "json":
                    return httpx.Response(200, json=json.loads(body), request=request)
                return httpx.Response(200, text=body, request=request)
        return httpx.Response(404, request=request)

    return handler


async def _run(provider: PackageProvider, name: str, handler) -> PackageInfo:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    try:
        return await provider.get_package(name)
    finally:
        await client.aclose()


async def test_npm_provider(read_fixture) -> None:
    handler = _router(read_fixture, [("registry.npmjs.org", "npm_react.json", "json")])
    info = await _run(NpmProvider(config=Config()), "react", handler)
    assert info.latest == "18.3.1"


async def test_crates_provider(read_fixture) -> None:
    handler = _router(read_fixture, [("crates.io", "crates_serde.json", "json")])
    info = await _run(CratesProvider(config=Config()), "serde", handler)
    assert info.latest == "1.0.228"


async def test_packagist_provider(read_fixture) -> None:
    handler = _router(read_fixture, [("repo.packagist.org", "packagist_monolog.json", "json")])
    info = await _run(PackagistProvider(config=Config()), "monolog/monolog", handler)
    assert info.latest == "3.6.0"


async def test_pub_provider(read_fixture) -> None:
    handler = _router(read_fixture, [("pub.dev", "pub_http.json", "json")])
    info = await _run(PubProvider(config=Config()), "http", handler)
    assert info.latest == "1.4.0"


async def test_rubygems_provider(read_fixture) -> None:
    handler = _router(
        read_fixture,
        [
            ("/api/v1/gems/", "rubygems_minitest_gem.json", "json"),
            ("/api/v1/versions/", "rubygems_minitest_versions.json", "json"),
        ],
    )
    info = await _run(RubyGemsProvider(config=Config()), "minitest", handler)
    assert info.latest == "5.25.4"


async def test_nuget_provider(read_fixture) -> None:
    handler = _router(
        read_fixture,
        [
            ("flatcontainer", "nuget_newtonsoft_index.json", "json"),
            ("registration", "nuget_newtonsoft_registration.json", "json"),
        ],
    )
    info = await _run(NuGetProvider(config=Config()), "Newtonsoft.Json", handler)
    assert info.latest == "13.0.4"


async def test_maven_provider(read_fixture) -> None:
    handler = _router(read_fixture, [("maven-metadata.xml", "maven_junit_metadata.xml", "text")])
    info = await _run(MavenProvider(config=Config()), "org.junit.jupiter:junit-jupiter", handler)
    assert info.latest == "5.12.2"


async def test_golang_provider(read_fixture) -> None:
    handler = _router(
        read_fixture,
        [
            ("/@v/list", "golang_mux_list.txt", "text"),
            (".info", "golang_mux_info.json", "json"),
        ],
    )
    info = await _run(GoModuleProvider(config=Config()), "github.com/gorilla/mux", handler)
    assert info.latest == "v1.8.1"


@pytest.mark.parametrize(
    ("provider_factory", "name"),
    [
        (lambda: NpmProvider(config=Config()), "missing"),
        (lambda: CratesProvider(config=Config()), "missing"),
        (lambda: PackagistProvider(config=Config()), "missing/missing"),
        (lambda: PubProvider(config=Config()), "missing"),
        (lambda: RubyGemsProvider(config=Config()), "missing"),
        (lambda: NuGetProvider(config=Config()), "Missing.Pkg"),
        (lambda: MavenProvider(config=Config()), "org.missing:missing"),
        (lambda: GoModuleProvider(config=Config()), "example.com/missing"),
    ],
)
async def test_provider_not_found(provider_factory, name: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    try:
        with pytest.raises(PackageNotFoundError):
            await provider_factory().get_package(name)
    finally:
        await client.aclose()


async def test_provider_network_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    try:
        with pytest.raises(PackageNotFoundError):
            await NpmProvider(config=Config()).get_package("react")
    finally:
        await client.aclose()


async def test_provider_empty_name_raises() -> None:
    with pytest.raises(PackageNotFoundError):
        await CratesProvider(config=Config()).get_package("   ")
