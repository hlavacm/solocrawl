"""Providers subcommand: list registered search and package providers."""

from __future__ import annotations

import argparse
import json
import sys

from solocrawl.core.discovery import (
    ProviderSummary,
    list_package_providers,
    list_search_providers,
    provider_label,
    provider_status_note,
)


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``providers`` subcommand."""
    parser = subparsers.add_parser(
        "providers",
        help="List registered search and package providers",
        description="Show which providers are registered, default vs. opt-in, and what they need.",
    )
    parser.add_argument(
        "--type",
        choices=("search", "package", "all"),
        default="all",
        help="Which provider type to list (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.set_defaults(command_handler=run)


def run(args: argparse.Namespace) -> int:
    """Run the providers subcommand."""
    search = list_search_providers() if args.type in ("search", "all") else []
    package = list_package_providers() if args.type in ("package", "all") else []

    if args.json:
        payload = {
            "search": [_summary_to_dict(item) for item in search],
            "package": [_summary_to_dict(item) for item in package],
        }
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        return 0

    blocks: list[str] = []
    if args.type in ("search", "all"):
        blocks.append(_format_block("Search providers", search))
    if args.type in ("package", "all"):
        blocks.append(_format_block("Package providers", package))
    sys.stdout.write("\n\n".join(blocks))
    sys.stdout.write("\n")
    return 0


def _summary_to_dict(item: ProviderSummary) -> dict[str, object]:
    data: dict[str, object] = {
        "name": item.name,
        "zero_config": item.zero_config,
        "required_env_key": item.required_env_key,
    }
    if item.ecosystem is not None:
        data["ecosystem"] = item.ecosystem
    return data


def _format_block(title: str, items: list[ProviderSummary]) -> str:
    lines = [f"{title}:"]
    if not items:
        lines.append("  (none)")
        return "\n".join(lines)

    width = max(len(provider_label(item)) for item in items)
    for item in items:
        status, note = provider_status_note(item)
        lines.append(f"  {provider_label(item).ljust(width)}  {status}{note}")
    return "\n".join(lines)
