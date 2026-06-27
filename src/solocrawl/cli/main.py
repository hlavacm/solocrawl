"""SoloCrawl CLI entry point."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from solocrawl.cli import batch, package, providers, research, scrape, search
from solocrawl.config import init_env
from solocrawl.logging_config import configure_logging

CommandHandler = Callable[[argparse.Namespace], int]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solocrawl",
        description="Self-hosted web search, scraping, and package-version lookup.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        metavar="COMMAND",
    )

    scrape.add_parser(subparsers)
    search.add_parser(subparsers)
    package.add_parser(subparsers)
    providers.add_parser(subparsers)
    research.add_parser(subparsers)
    batch.add_parser(subparsers)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the SoloCrawl CLI."""
    init_env()
    configure_logging()
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    handler = getattr(args, "command_handler", None)
    if handler is None:
        parser.print_help()
        raise SystemExit(2)

    raise SystemExit(handler(args))


if __name__ == "__main__":
    main()
