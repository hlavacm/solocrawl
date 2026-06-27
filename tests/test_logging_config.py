"""Tests for shared logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from solocrawl.logging_config import configure_logging


def test_configure_logging_writes_to_file(tmp_path: Path, monkeypatch) -> None:
    log_file = tmp_path / "mcp.log"
    monkeypatch.setenv("SOLOCRAWL_LOG_LEVEL", "INFO")
    monkeypatch.setenv("SOLOCRAWL_LOG_FILE", str(log_file))

    configure_logging()
    logging.getLogger("solocrawl.test").info("hello from mcp")

    assert log_file.read_text(encoding="utf-8").strip() == "INFO: hello from mcp"


def test_configure_logging_unknown_level_defaults_to_warning(monkeypatch) -> None:
    monkeypatch.setenv("SOLOCRAWL_LOG_LEVEL", "not-a-level")
    monkeypatch.delenv("SOLOCRAWL_LOG_FILE", raising=False)

    configure_logging()

    assert logging.getLogger().level == logging.WARNING
