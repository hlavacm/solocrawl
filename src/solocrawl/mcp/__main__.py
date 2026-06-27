"""Entry point for ``python -m solocrawl.mcp`` and the ``solocrawl-mcp`` console script."""

from __future__ import annotations

import contextlib
import os
import signal
import sys

import anyio

from solocrawl import __version__
from solocrawl.config import init_env
from solocrawl.core.fetch import close_browser, close_client
from solocrawl.logging_config import configure_logging
from solocrawl.mcp.server import REPO_URL, create_server


def _log_startup_info() -> None:
    """Print a short SoloCrawl banner to stderr (safe for stdio MCP transport)."""
    message = (
        f"\nSoloCrawl MCP {__version__}\n"
        "Self-hosted web search, scraping, and package-version lookup\n"
        "Tools: web_search, scrape, research, package_version, list_providers\n"
        f"{REPO_URL}\n"
    )
    sys.stderr.write(message)


async def _cleanup_runtime() -> None:
    await close_client()
    await close_browser()


def _cleanup_runtime_sync() -> None:
    """Best-effort runtime cleanup when the server loop was interrupted."""
    with contextlib.suppress(Exception):
        anyio.run(_cleanup_runtime)


def _exit_on_signal(signum: int, frame: object) -> None:
    """Exit immediately on SIGINT/SIGTERM.

    Installed before ``anyio.run()`` so FastMCP's stdio loop cannot swallow the
    first Ctrl+C while blocked on stdin.
    """
    del frame
    _cleanup_runtime_sync()
    exit_code = 130 if signum == signal.SIGINT else 143
    os._exit(exit_code)


def main() -> None:
    """Run the SoloCrawl MCP server over stdio."""
    init_env()
    configure_logging()
    _log_startup_info()
    if sys.platform == "win32":
        with contextlib.suppress(KeyboardInterrupt):
            create_server().run(show_banner=False)
        return

    signal.signal(signal.SIGINT, _exit_on_signal)
    signal.signal(signal.SIGTERM, _exit_on_signal)
    with contextlib.suppress(KeyboardInterrupt):
        create_server().run(show_banner=False)


if __name__ == "__main__":
    main()
