"""Tests for package registry providers."""

from __future__ import annotations

import json

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.packages import clear_registry, select_provider_for_ecosystem
from solocrawl.core.packages.providers import crates as crates_module
from solocrawl.core.packages.providers import golang as golang_module
from solocrawl.core.packages.providers import maven as maven_module
from solocrawl.core.packages.providers import npm as npm_module
from solocrawl.core.packages.providers import nuget as nuget_module
from solocrawl.core.packages.providers import packagist as packagist_module
from solocrawl.core.packages.providers import pub as pub_module
from solocrawl.core.packages.providers import pypi as pypi_module
from solocrawl.core.packages.providers import rubygems as rubygems_module
from solocrawl.core.packages.providers import swift as swift_module
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.providers.crates import CratesProvider, _parse_crates_payload
from solocrawl.core.packages.providers.golang import (
    GoModuleProvider,
    _parse_go_module_payload,
    _parse_go_version_list,
)
from solocrawl.core.packages.providers.maven import MavenProvider, _parse_maven_metadata
from solocrawl.core.packages.providers.npm import NpmProvider, _parse_npm_payload
from solocrawl.core.packages.providers.nuget import NuGetProvider, _parse_nuget_payload
from solocrawl.core.packages.providers.packagist import PackagistProvider, _parse_packagist_payload
from solocrawl.core.packages.providers.pub import PubProvider, _parse_pub_payload
from solocrawl.core.packages.providers.pypi import PyPIProvider, _parse_pypi_payload
from solocrawl.core.packages.providers.rubygems import RubyGemsProvider, _parse_rubygems_payload
from solocrawl.core.packages.providers.swift import SwiftProvider

DEFAULT_ECOSYSTEMS = (
    "pypi",
    "npm",
    "packagist",
    "crates",
    "nuget",
    "maven",
    "rubygems",
    "go",
    "pub",
    "swift",
)


@pytest.fixture(autouse=True)
def package_providers_registered() -> None:
    clear_registry()
    pypi_module.register("pypi", ecosystem="pypi", zero_config=True)(PyPIProvider)
    npm_module.register("npm", ecosystem="npm", zero_config=True)(NpmProvider)
    packagist_module.register("packagist", ecosystem="packagist", zero_config=True)(
        PackagistProvider
    )
    crates_module.register("crates", ecosystem="crates", zero_config=True)(CratesProvider)
    nuget_module.register("nuget", ecosystem="nuget", zero_config=True)(NuGetProvider)
    maven_module.register("maven", ecosystem="maven", zero_config=True)(MavenProvider)
    rubygems_module.register("rubygems", ecosystem="rubygems", zero_config=True)(RubyGemsProvider)
    golang_module.register("go", ecosystem="go", zero_config=True)(GoModuleProvider)
    pub_module.register("pub", ecosystem="pub", zero_config=True)(PubProvider)
    swift_module.register("swift", ecosystem="swift", zero_config=True)(SwiftProvider)


def test_pypi_parse_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("pypi_requests.json"))
    info = _parse_pypi_payload("requests", payload, constraint=None, allow_prerelease=False)

    assert info.latest == "2.32.3"
    assert info.repository == "https://github.com/psf/requests"
    assert info.versions == ["2.32.0", "2.31.0"]


def test_pypi_constraint(read_fixture) -> None:
    payload = json.loads(read_fixture("pypi_requests.json"))
    info = _parse_pypi_payload(
        "requests",
        payload,
        constraint=">=2.32,<2.32.3",
        allow_prerelease=False,
    )

    assert info.latest == "2.32.0"


def test_npm_parse_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("npm_react.json"))
    info = _parse_npm_payload("react", payload, constraint=None, allow_prerelease=False)

    assert info.latest == "18.3.1"
    assert info.homepage == "https://react.dev/"


def test_npm_constraint(read_fixture) -> None:
    payload = json.loads(read_fixture("npm_react.json"))
    info = _parse_npm_payload(
        "react",
        payload,
        constraint=">=18,<19",
        allow_prerelease=False,
    )

    assert info.latest == "18.3.1"


def test_packagist_parse_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("packagist_monolog.json"))
    info = _parse_packagist_payload(
        "monolog/monolog",
        payload,
        constraint=None,
        allow_prerelease=False,
    )

    assert info.latest == "3.6.0"
    assert info.repository == "https://github.com/Seldaek/monolog"


def test_crates_parse_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("crates_serde.json"))
    info = _parse_crates_payload("serde", payload, constraint=None, allow_prerelease=False)

    assert info.latest == "1.0.228"
    assert info.repository == "https://github.com/serde-rs/serde"


def test_crates_constraint(read_fixture) -> None:
    payload = json.loads(read_fixture("crates_serde.json"))
    info = _parse_crates_payload(
        "serde",
        payload,
        constraint=">=1.0.227,<1.0.228",
        allow_prerelease=False,
    )

    assert info.latest == "1.0.227"


def test_nuget_parse_fixture(read_fixture) -> None:
    index_payload = json.loads(read_fixture("nuget_newtonsoft_index.json"))
    registration_payload = json.loads(read_fixture("nuget_newtonsoft_registration.json"))
    info = _parse_nuget_payload(
        "Newtonsoft.Json",
        index_payload,
        registration_payload,
        constraint=None,
        allow_prerelease=False,
    )

    assert info.latest == "13.0.4"
    assert info.repository == "https://www.newtonsoft.com/json"


def test_maven_parse_fixture(read_fixture) -> None:
    metadata_xml = read_fixture("maven_junit_metadata.xml")
    info = _parse_maven_metadata(
        "org.junit.jupiter:junit-jupiter",
        metadata_xml,
        constraint=None,
        allow_prerelease=False,
    )

    assert info.latest == "5.12.2"


def test_maven_constraint(read_fixture) -> None:
    metadata_xml = read_fixture("maven_junit_metadata.xml")
    info = _parse_maven_metadata(
        "org.junit.jupiter:junit-jupiter",
        metadata_xml,
        constraint=">=5.12.1,<5.12.2",
        allow_prerelease=False,
    )

    assert info.latest == "5.12.1"


def test_rubygems_parse_fixture(read_fixture) -> None:
    gem_payload = json.loads(read_fixture("rubygems_minitest_gem.json"))
    versions_payload = json.loads(read_fixture("rubygems_minitest_versions.json"))
    info = _parse_rubygems_payload(
        "minitest",
        gem_payload,
        versions_payload,
        constraint=None,
        allow_prerelease=False,
    )

    assert info.latest == "5.25.4"
    assert info.repository == "https://github.com/minitest/minitest"


def test_go_parse_fixture(read_fixture) -> None:
    versions = _parse_go_version_list(read_fixture("golang_mux_list.txt"))
    info_payload = json.loads(read_fixture("golang_mux_info.json"))
    info = _parse_go_module_payload(
        "github.com/gorilla/mux",
        versions,
        info_payload,
        constraint=None,
        allow_prerelease=False,
    )

    assert info.latest == "v1.8.1"
    assert info.repository == "https://github.com/gorilla/mux"


def test_go_constraint(read_fixture) -> None:
    versions = _parse_go_version_list(read_fixture("golang_mux_list.txt"))
    info = _parse_go_module_payload(
        "github.com/gorilla/mux",
        versions,
        {},
        constraint=">=1.8.0,<1.8.1",
        allow_prerelease=False,
    )

    assert info.latest == "v1.8.0"


def test_pub_parse_fixture(read_fixture) -> None:
    payload = json.loads(read_fixture("pub_http.json"))
    info = _parse_pub_payload("http", payload, constraint=None, allow_prerelease=False)

    assert info.latest == "1.4.0"
    assert "github.com/dart-lang/http" in (info.repository or "")


async def test_pypi_provider_uses_shared_client(read_fixture) -> None:
    fixture_body = read_fixture("pypi_requests.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json.loads(fixture_body), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = PyPIProvider(config=Config())
    info = await provider.get_package("requests")

    assert info.latest == "2.32.3"
    await client.aclose()


async def test_pypi_provider_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = PyPIProvider(config=Config())
    with pytest.raises(PackageNotFoundError):
        await provider.get_package("missing-package")

    await client.aclose()


async def test_pypi_provider_encodes_package_name() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(404, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = PyPIProvider(config=Config())
    with pytest.raises(PackageNotFoundError):
        await provider.get_package("evil/../name")

    assert requested == ["https://pypi.org/pypi/evil%2F..%2Fname/json"]
    await client.aclose()


def test_default_providers_are_selectable() -> None:
    for ecosystem in DEFAULT_ECOSYSTEMS:
        assert select_provider_for_ecosystem(ecosystem, Config()) is not None
