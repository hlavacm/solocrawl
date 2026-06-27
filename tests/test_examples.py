"""Smoke test for the library example script."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from solocrawl.core.models import SearchResult


@pytest.mark.asyncio
async def test_library_search_example_runs() -> None:
    from examples.library_search import main

    sample = [
        SearchResult(
            title="Example",
            url="https://example.com",
            snippet="snippet",
            source="wikipedia",
        )
    ]
    with (
        patch("examples.library_search.select_providers", return_value=[object()]),
        patch(
            "examples.library_search.federated_search",
            new=AsyncMock(return_value=sample),
        ),
        patch("examples.library_search.close_client", new=AsyncMock(return_value=None)),
    ):
        await main()
