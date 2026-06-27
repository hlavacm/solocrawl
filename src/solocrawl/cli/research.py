"""Research subcommand: federated search + scrape + aggregated report."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from solocrawl.core.fetch import close_browser, close_client
from solocrawl.core.research import MAX_RESEARCH_DEPTH, research, research_to_markdown
from solocrawl.core.search import (
    providers as _search_providers,  # noqa: F401  (registers providers)
)


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``research`` subcommand."""
    parser = subparsers.add_parser(
        "research",
        help="Search, scrape the top results, and print an aggregated report",
        description="Federated search, scrape the top results, and aggregate them with sources.",
    )
    parser.add_argument("query", help="Research query")
    parser.add_argument(
        "--depth",
        type=int,
        default=3,
        metavar="N",
        help="Number of top results to scrape and aggregate (default: 3)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output documents as JSON",
    )
    parser.set_defaults(command_handler=run)


def run(args: argparse.Namespace) -> int:
    """Run the research subcommand."""
    return asyncio.run(_research(args))


async def _research(args: argparse.Namespace) -> int:
    query = args.query.strip()
    if not query:
        print("error: query must not be empty", file=sys.stderr)
        return 1
    if args.depth <= 0:
        print("error: --depth must be positive", file=sys.stderr)
        return 1
    if args.depth > MAX_RESEARCH_DEPTH:
        print(f"error: --depth must be at most {MAX_RESEARCH_DEPTH}", file=sys.stderr)
        return 1

    try:
        documents = await research(query, depth=args.depth)
    finally:
        await close_client()
        await close_browser()

    if args.json:
        payload = [asdict(document) for document in documents]
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        return 0

    if not documents:
        print("No results.", file=sys.stderr)
        return 0

    sys.stdout.write(research_to_markdown(query, documents))
    sys.stdout.write("\n")
    return 0
