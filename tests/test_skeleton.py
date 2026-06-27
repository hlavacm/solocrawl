"""Smoke tests for the project skeleton."""

import importlib
import pkgutil

import solocrawl


def test_version_is_set() -> None:
    assert solocrawl.__version__ == "1.0.0"


def test_all_submodules_are_importable() -> None:
    """Every package under solocrawl must import without error."""
    prefix = f"{solocrawl.__name__}."
    for module_info in pkgutil.walk_packages(solocrawl.__path__, prefix):
        importlib.import_module(module_info.name)
