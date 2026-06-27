"""Package subcommand: resolve package versions from official registries."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from solocrawl.config import load_config
from solocrawl.core.fetch import close_client
from solocrawl.core.packages import select_provider_for_ecosystem
from solocrawl.core.packages.providers import (  # noqa: F401
    crates,
    golang,
    maven,
    npm,
    nuget,
    packagist,
    pub,
    pypi,
    rubygems,
    swift,
)
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.resolver import InvalidConstraintError

SUPPORTED_ECOSYSTEMS = (
    "pypi",
    "npm",
    "packagist",
    "crates",
    "nuget",
    "maven",
    "rubygems",
    "go",
    "pub",
    "swift",
)


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``package`` subcommand."""
    parser = subparsers.add_parser(
        "package",
        help="Look up package versions from an official registry",
        description="Resolve the latest or constraint-satisfying version of a package.",
    )
    parser.add_argument("name", help="Package name")
    parser.add_argument(
        "--ecosystem",
        required=True,
        choices=SUPPORTED_ECOSYSTEMS,
        help=(
            "Registry ecosystem: pypi, npm, packagist, crates, nuget, maven, rubygems, go, pub, "
            "or swift (owner/repo on GitHub)"
        ),
    )
    parser.add_argument(
        "--constraint",
        help="Optional version constraint (e.g. '>=4.2,<5')",
    )
    parser.add_argument(
        "--allow-prerelease",
        action="store_true",
        help="Allow pre-release versions when resolving",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output package info as JSON",
    )
    parser.set_defaults(command_handler=run)


def run(args: argparse.Namespace) -> int:
    """Run the package subcommand."""
    return asyncio.run(_package(args))


async def _package(args: argparse.Namespace) -> int:
    package_name = args.name.strip()
    if not package_name:
        print("error: package name must not be empty", file=sys.stderr)
        return 1

    config = load_config()
    provider = select_provider_for_ecosystem(args.ecosystem, config)
    if provider is None:
        print(
            f"error: no provider available for ecosystem {args.ecosystem!r}",
            file=sys.stderr,
        )
        return 1

    try:
        info = await provider.get_package(
            package_name,
            constraint=args.constraint,
            allow_prerelease=args.allow_prerelease,
        )
    except InvalidConstraintError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except PackageNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        await close_client()

    if args.json:
        sys.stdout.write(json.dumps(asdict(info), indent=2, ensure_ascii=False))
        sys.stdout.write("\n")
        return 0

    print(f"{info.name} ({info.ecosystem})")
    print(f"latest: {info.latest}")
    if info.versions:
        print(f"previous: {', '.join(info.versions)}")
    if info.repository:
        print(f"repository: {info.repository}")
    if info.homepage:
        print(f"homepage: {info.homepage}")
    return 0
