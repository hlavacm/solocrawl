"""Example: federated search from Python."""

from __future__ import annotations

import asyncio

from solocrawl.config import load_config
from solocrawl.core.fetch import close_client
from solocrawl.core.search import federated_search, select_providers
from solocrawl.core.search.providers import duckduckgo, stackexchange, wikipedia  # noqa: F401


async def main() -> None:
    config = load_config()
    providers = select_providers(config)
    results = await federated_search(providers, "python asyncio", limit=3)
    for index, result in enumerate(results, start=1):
        print(f"{index}. {result.title}")
        print(f"   {result.url} [{result.source}]")
    await close_client()


if __name__ == "__main__":
    asyncio.run(main())
