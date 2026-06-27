"""Batch subcommand: scrape several URLs at once (bounded concurrency)."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

from solocrawl.cli.document import render_fetch_document
from solocrawl.core.fetch import close_browser, close_client, fetch
from solocrawl.core.models import FetchResult


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``batch`` subcommand."""
    parser = subparsers.add_parser(
        "batch",
        help="Scrape several URLs at once",
        description="Fetch multiple URLs concurrently and print or save the extracted markdown.",
    )
    parser.add_argument("urls", nargs="*", help="URLs to scrape")
    parser.add_argument(
        "--from-file",
        type=Path,
        metavar="FILE",
        help="Read URLs from FILE (one per line; '#' comments allowed)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        metavar="DIR",
        help="Write each result to DIR/<hash>.md instead of stdout",
    )
    parser.add_argument(
        "--force-browser",
        action="store_true",
        help="Use browser rendering when httpx content is insufficient",
    )
    parser.set_defaults(command_handler=run)


def run(args: argparse.Namespace) -> int:
    """Run the batch subcommand."""
    return asyncio.run(_batch(args))


async def _batch(args: argparse.Namespace) -> int:
    urls = _collect_urls(args.urls, args.from_file)
    if isinstance(urls, str):  # error message
        print(f"error: {urls}", file=sys.stderr)
        return 1
    if not urls:
        print("error: no URLs provided", file=sys.stderr)
        return 1

    out_dir: Path | None = args.out_dir
    if out_dir is not None:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"error: cannot create {out_dir}: {exc}", file=sys.stderr)
            return 1

    try:
        outcomes = await asyncio.gather(
            *(fetch(url, force_browser=args.force_browser) for url in urls),
            return_exceptions=True,
        )
    finally:
        await close_client()
        await close_browser()

    failures = 0
    for url, outcome in zip(urls, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            failures += 1
            print(f"error: {url}: {outcome}", file=sys.stderr)
            continue
        if not _emit(url, outcome, out_dir):
            failures += 1

    return 1 if failures else 0


def _collect_urls(cli_urls: list[str], from_file: Path | None) -> list[str] | str:
    urls = [url.strip() for url in cli_urls if url.strip()]
    if from_file is not None:
        try:
            lines = from_file.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            return f"cannot read {from_file}: {exc}"
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                urls.append(stripped)
    return urls


def _emit(url: str, result: FetchResult, out_dir: Path | None) -> bool:
    document = render_fetch_document(result)
    if out_dir is not None:
        name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        path = out_dir / f"{name}.md"
        try:
            path.write_text(document, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {path}: {exc}", file=sys.stderr)
            return False
        print(f"{url} -> {path}", file=sys.stderr)
        return True

    sys.stdout.write(f"# {url}\n\n{document}\n\n---\n\n")
    return True
