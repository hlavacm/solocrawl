"""Scrape subcommand: fetch a URL and output markdown."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import httpx

from solocrawl.cli.document import render_fetch_document
from solocrawl.core.fetch import (
    FetchUrlError,
    RobotsDisallowedError,
    close_browser,
    close_client,
    fetch,
)


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``scrape`` subcommand."""
    parser = subparsers.add_parser(
        "scrape",
        help="Fetch a URL and output extracted markdown",
        description="Fetch a URL and print extracted markdown to stdout.",
    )
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument(
        "--out",
        type=Path,
        metavar="FILE",
        help="Write markdown to FILE instead of stdout",
    )
    parser.add_argument(
        "--force-browser",
        action="store_true",
        help="Use browser rendering when httpx content is insufficient",
    )
    parser.set_defaults(command_handler=run)


def run(args: argparse.Namespace) -> int:
    """Run the scrape subcommand."""
    return asyncio.run(_scrape(args.url, out=args.out, force_browser=args.force_browser))


async def _scrape(url: str, *, out: Path | None, force_browser: bool) -> int:
    try:
        result = await fetch(url, force_browser=force_browser)
    except (FetchUrlError, RobotsDisallowedError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPStatusError as exc:
        print(
            f"error: HTTP {exc.response.status_code} for {url}",
            file=sys.stderr,
        )
        return 1
    except httpx.RequestError as exc:
        print(f"error: network error: {exc}", file=sys.stderr)
        return 1
    finally:
        await close_client()
        await close_browser()

    document = render_fetch_document(result)

    if out is not None:
        try:
            out.write_text(document, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write to {out}: {exc}", file=sys.stderr)
            return 1
        return 0

    sys.stdout.write(document)
    if not document.endswith("\n"):
        sys.stdout.write("\n")
    return 0
