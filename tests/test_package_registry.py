"""Tests for package provider registration and selection."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from solocrawl.config import Config
from solocrawl.core.models import PackageInfo
from solocrawl.core.packages import (
    clear_registry,
    get_registration,
    list_registrations,
    register,
    select_provider_for_ecosystem,
    select_providers,
)


class DummyPyPIProvider:
    name = "pypi"
    ecosystem = "pypi"
    zero_config = True

    async def get_package(
        self,
        name: str,
        *,
        constraint: str | None = None,
        allow_prerelease: bool = False,
    ) -> PackageInfo:
        return PackageInfo(name=name, ecosystem="pypi", latest="1.0.0")


class DummyOptInProvider:
    name = "crates"
    ecosystem = "crates"
    zero_config = False

    async def get_package(
        self,
        name: str,
        *,
        constraint: str | None = None,
        allow_prerelease: bool = False,
    ) -> PackageInfo:
        return PackageInfo(name=name, ecosystem="crates", latest="0.1.0")


@pytest.fixture
def dummy_package_providers() -> Generator[None]:
    clear_registry()
    register("pypi", ecosystem="pypi", zero_config=True)(DummyPyPIProvider)
    register("crates", ecosystem="crates")(DummyOptInProvider)
    yield
    clear_registry()


def test_package_registry_lists_providers(dummy_package_providers: None) -> None:
    names = {registration.name for registration in list_registrations()}

    assert names == {"pypi", "crates"}


def test_package_selector_zero_config(dummy_package_providers: None) -> None:
    providers = select_providers(Config(), env={})
    names = {provider.name for provider in providers}

    assert names == {"pypi"}


def test_package_selector_opt_in(dummy_package_providers: None) -> None:
    config = Config(enabled_providers=frozenset({"crates"}))
    providers = select_providers(config, env={})
    names = {provider.name for provider in providers}

    assert names == {"pypi", "crates"}


def test_select_provider_for_ecosystem(dummy_package_providers: None) -> None:
    provider = select_provider_for_ecosystem("pypi", Config(), env={})

    assert provider is not None
    assert provider.ecosystem == "pypi"


def test_get_registration_metadata(dummy_package_providers: None) -> None:
    registration = get_registration("pypi")

    assert registration is not None
    assert registration.ecosystem == "pypi"
    assert registration.zero_config is True
