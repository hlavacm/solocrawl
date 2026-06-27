"""Search subcommand: federated web search across providers."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from solocrawl.config import Config, load_config
from solocrawl.core.fetch import close_browser, close_client
from solocrawl.core.models import SearchResult
from solocrawl.core.search import federated_search, select_providers
from solocrawl.core.search import (
    providers as _search_providers,  # noqa: F401  (registers providers)
)


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``search`` subcommand."""
    parser = subparsers.add_parser(
        "search",
        help="Run federated web search across configured providers",
        description="Search the web using the default provider set and print unified results.",
    )
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        metavar="N",
        help="Maximum number of results to return (default: 5)",
    )
    parser.add_argument(
        "--sources",
        metavar="NAMES",
        help="Comma-separated provider names to use (default: all enabled providers)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.set_defaults(command_handler=run)


def run(args: argparse.Namespace) -> int:
    """Run the search subcommand."""
    return asyncio.run(_search(args))


async def _search(args: argparse.Namespace) -> int:
    query = args.query.strip()
    if not query:
        print("error: query must not be empty", file=sys.stderr)
        return 1

    limit = args.limit
    if limit <= 0:
        print("error: --limit must be positive", file=sys.stderr)
        return 1

    config = load_config()
    requested: frozenset[str] | None = None
    if args.sources:
        requested = frozenset(name.strip() for name in args.sources.split(",") if name.strip())
        config = Config(
            concurrency=config.concurrency,
            proxy=config.proxy,
            browser=config.browser,
            fetch=config.fetch,
            enabled_providers=requested,
        )

    providers = select_providers(config)
    if requested is not None:
        providers = [provider for provider in providers if provider.name in requested]
        if not providers:
            print(
                f"error: no matching providers for sources: {args.sources}",
                file=sys.stderr,
            )
            return 1
    elif not providers:
        print("error: no search providers are enabled", file=sys.stderr)
        return 1

    try:
        results = await federated_search(providers, query, limit=limit)
    finally:
        await close_client()
        await close_browser()

    if args.json:
        payload = [_result_to_dict(result) for result in results]
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        return 0

    if not results:
        print("No results.", file=sys.stderr)
        return 0

    for index, result in enumerate(results, start=1):
        _print_result(index, result)
    return 0


def _result_to_dict(result: SearchResult) -> dict[str, object]:
    data = asdict(result)
    data.pop("raw", None)
    return data


def _print_result(index: int, result: SearchResult) -> None:
    print(f"{index}. {result.title}")
    print(f"   {result.url}")
    print(f"   source: {result.source}  score: {result.score:.4f}")
    if result.snippet:
        print(f"   {result.snippet}")
    print()
