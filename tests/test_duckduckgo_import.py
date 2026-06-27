"""Coverage for the ddgs import resolution in the DuckDuckGo provider."""

from __future__ import annotations

import builtins
import sys
import types

import pytest

from solocrawl.core.search.providers.duckduckgo import _import_ddgs


def _block_ddgs(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        if name == "ddgs":
            raise ImportError("no ddgs")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_import_ddgs_falls_back_to_duckduckgo_search(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("duckduckgo_search")
    fake_module.DDGS = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "duckduckgo_search", fake_module)
    _block_ddgs(monkeypatch)

    assert _import_ddgs() is object


def test_import_ddgs_raises_when_nothing_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "duckduckgo_search", raising=False)
    _block_ddgs(monkeypatch)

    with pytest.raises(ImportError):
        _import_ddgs()
