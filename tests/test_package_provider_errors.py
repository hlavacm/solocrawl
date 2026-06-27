"""Empty-name and network-error coverage for every package provider."""

from __future__ import annotations

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.providers.crates import CratesProvider
from solocrawl.core.packages.providers.golang import GoModuleProvider
from solocrawl.core.packages.providers.maven import MavenProvider
from solocrawl.core.packages.providers.npm import NpmProvider
from solocrawl.core.packages.providers.nuget import NuGetProvider
from solocrawl.core.packages.providers.packagist import PackagistProvider
from solocrawl.core.packages.providers.pub import PubProvider
from solocrawl.core.packages.providers.pypi import PyPIProvider
from solocrawl.core.packages.providers.rubygems import RubyGemsProvider
from solocrawl.core.packages.providers.swift import SwiftProvider

_PROVIDERS = [
    CratesProvider,
    GoModuleProvider,
    MavenProvider,
    NpmProvider,
    NuGetProvider,
    PackagistProvider,
    PubProvider,
    PyPIProvider,
    RubyGemsProvider,
    SwiftProvider,
]


@pytest.mark.parametrize("provider_cls", _PROVIDERS)
async def test_empty_name_raises(provider_cls) -> None:
    with pytest.raises(PackageNotFoundError):
        await provider_cls(config=Config()).get_package("   ")


@pytest.mark.parametrize("provider_cls", _PROVIDERS)
async def test_network_error_raises(provider_cls) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)
    try:
        with pytest.raises(PackageNotFoundError):
            await provider_cls(config=Config()).get_package("some/name")
    finally:
        await client.aclose()


def test_providers_instantiate_without_config() -> None:
    # Exercises the ``config is None -> load_config()`` constructor branch.
    for provider_cls in _PROVIDERS:
        assert provider_cls() is not None
