"""Live smoke tests against the real network.

Deselected by default (``addopts = -m 'not live'``). Run explicitly with:

    pytest -m live

These are intentionally tolerant — they confirm the end-to-end paths work against
the live web, not exact content.
"""

from __future__ import annotations

import pytest

from solocrawl.config import Config
from solocrawl.core.fetch import close_client, fetch
from solocrawl.core.packages import providers as _package_providers  # noqa: F401  (registers)
from solocrawl.core.packages import select_provider_for_ecosystem
from solocrawl.core.search import federated_search, select_providers
from solocrawl.core.search import providers as _search_providers  # noqa: F401  (registers)

pytestmark = pytest.mark.live


async def test_federated_search_live() -> None:
    results = await federated_search(select_providers(Config()), "python asyncio", limit=3)
    await close_client()
    assert len(results) >= 1
    assert all(result.url for result in results)


async def test_fetch_live() -> None:
    result = await fetch("https://example.com")
    await close_client()
    assert result.status == 200
    assert result.content.strip()


async def test_package_pypi_live() -> None:
    provider = select_provider_for_ecosystem("pypi", Config())
    assert provider is not None
    info = await provider.get_package("requests")
    await close_client()
    assert info.latest


async def test_package_swift_live() -> None:
    provider = select_provider_for_ecosystem("swift", Config())
    assert provider is not None
    info = await provider.get_package("apple/swift-argument-parser")
    await close_client()
    assert info.latest
