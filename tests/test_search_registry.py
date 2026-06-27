"""Tests for search provider registration and selection."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from solocrawl.config import Config
from solocrawl.core.models import SearchResult
from solocrawl.core.search import (
    clear_registry,
    get_registration,
    list_registrations,
    register,
    select_providers,
)


class DummyZeroConfigProvider:
    name = "dummy_zero"
    zero_config = True

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"zero:{query}",
                url="https://example.com/zero",
                snippet="zero config",
                source=self.name,
            )
        ]


class DummyOptInProvider:
    name = "dummy_optin"
    zero_config = False

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"optin:{query}",
                url="https://example.com/optin",
                snippet="opt in",
                source=self.name,
            )
        ]


class DummyKeyedOptInProvider:
    name = "dummy_keyed"
    zero_config = False

    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"keyed:{query}",
                url="https://example.com/keyed",
                snippet="needs key",
                source=self.name,
            )
        ]


@pytest.fixture
def dummy_providers() -> Generator[None]:
    clear_registry()
    register("dummy_zero", zero_config=True)(DummyZeroConfigProvider)
    register("dummy_optin")(DummyOptInProvider)
    register("dummy_keyed", required_env_key="SOLOCRAWL_DUMMY_API_KEY")(DummyKeyedOptInProvider)
    yield
    clear_registry()


def test_registry_lists_registered_providers(dummy_providers: None) -> None:
    names = {registration.name for registration in list_registrations()}

    assert names == {"dummy_zero", "dummy_optin", "dummy_keyed"}


def test_get_registration_returns_metadata(dummy_providers: None) -> None:
    registration = get_registration("dummy_keyed")

    assert registration is not None
    assert registration.zero_config is False
    assert registration.required_env_key == "SOLOCRAWL_DUMMY_API_KEY"


def test_provider_selection_zero_config_always_included(dummy_providers: None) -> None:
    providers = select_providers(Config(), env={})
    names = {provider.name for provider in providers}

    assert "dummy_zero" in names
    assert "dummy_optin" not in names
    assert "dummy_keyed" not in names


def test_provider_selection_opt_in_when_enabled(dummy_providers: None) -> None:
    config = Config(enabled_providers=frozenset({"dummy_optin"}))
    providers = select_providers(config, env={})
    names = {provider.name for provider in providers}

    assert "dummy_zero" in names
    assert "dummy_optin" in names
    assert "dummy_keyed" not in names


def test_provider_selection_key_required_only_with_key(dummy_providers: None) -> None:
    config = Config(enabled_providers=frozenset({"dummy_keyed"}))

    without_key = select_providers(config, env={})
    assert {provider.name for provider in without_key} == {"dummy_zero"}

    with_key = select_providers(
        config,
        env={"SOLOCRAWL_DUMMY_API_KEY": "secret"},
    )
    names = {provider.name for provider in with_key}
    assert names == {"dummy_zero", "dummy_keyed"}


@pytest.mark.asyncio
async def test_dummy_provider_search_returns_results(dummy_providers: None) -> None:
    provider = DummyZeroConfigProvider()
    results = await provider.search("hello", limit=3)

    assert len(results) == 1
    assert results[0].source == "dummy_zero"
    assert "hello" in results[0].title
