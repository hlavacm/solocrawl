"""Shared pytest fixtures for fetch and extract tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from solocrawl.core.fetch.browser import reset_browser_state_for_testing
from solocrawl.core.fetch.cache import reset_cache
from solocrawl.core.fetch.client import close_client, set_client_for_testing
from solocrawl.core.fetch.concurrency import reset_concurrency_state
from solocrawl.core.fetch.robots import reset_robots_cache

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def read_fixture(fixtures_dir: Path):
    def _read(name: str) -> str:
        return (fixtures_dir / name).read_text(encoding="utf-8")

    return _read


@pytest.fixture
def article_html(read_fixture):
    return read_fixture("article.html")


@pytest.fixture(autouse=True)
async def reset_fetch_runtime_state() -> AsyncGenerator[None]:
    await close_client()
    await reset_concurrency_state()
    await reset_browser_state_for_testing()
    await set_client_for_testing(None)
    reset_robots_cache()
    reset_cache()
    yield
    await close_client()
    await reset_concurrency_state()
    await reset_browser_state_for_testing()
    await set_client_for_testing(None)
    reset_robots_cache()
    reset_cache()
