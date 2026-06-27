"""Tests for the MCP entry point (``solocrawl.mcp.__main__``)."""

from __future__ import annotations

import signal
from unittest.mock import MagicMock

import pytest

from solocrawl.mcp import __main__ as mcp_main


def test_log_startup_info(capsys: pytest.CaptureFixture[str]) -> None:
    mcp_main._log_startup_info()
    err = capsys.readouterr().err
    assert "SoloCrawl MCP" in err
    assert "web_search" in err
    assert "research" in err


def test_cleanup_runtime_sync_is_safe() -> None:
    # No shared client/browser exist -> must run without raising.
    mcp_main._cleanup_runtime_sync()


def test_exit_on_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    codes: list[int] = []
    monkeypatch.setattr(mcp_main.os, "_exit", lambda code: codes.append(code))
    monkeypatch.setattr(mcp_main, "_cleanup_runtime_sync", lambda: None)

    mcp_main._exit_on_signal(signal.SIGINT, None)
    mcp_main._exit_on_signal(signal.SIGTERM, None)

    assert codes == [130, 143]


def test_main_runs_server(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = MagicMock()
    monkeypatch.setattr(mcp_main, "create_server", lambda: fake_server)
    monkeypatch.setattr(mcp_main.signal, "signal", lambda *_args: None)

    mcp_main.main()

    fake_server.run.assert_called_once()
