"""Shared logging setup for CLI and MCP entry points."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def configure_logging() -> None:
    """Configure root logging from ``SOLOCRAWL_LOG_*`` environment variables.

    Logs always go to stderr (safe for MCP stdio transport). When
    ``SOLOCRAWL_LOG_FILE`` is set, the same messages are also appended to that file.
    """
    level_name = os.environ.get("SOLOCRAWL_LOG_LEVEL", "WARNING").strip().upper()
    level = _LOG_LEVELS.get(level_name, logging.WARNING)
    formatter = logging.Formatter("%(levelname)s: %(message)s")

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(level)
    root.addHandler(stderr_handler)

    log_file = os.environ.get("SOLOCRAWL_LOG_FILE", "").strip()
    if log_file:
        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
