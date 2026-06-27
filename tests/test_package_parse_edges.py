"""Edge-case tests for package payload parsing (invalid / empty responses)."""

from __future__ import annotations

import pytest

from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.providers.crates import _parse_crates_payload
from solocrawl.core.packages.providers.golang import (
    _parse_go_module_payload,
    _parse_go_version_list,
)
from solocrawl.core.packages.providers.maven import _parse_maven_metadata
from solocrawl.core.packages.providers.npm import _parse_npm_payload
from solocrawl.core.packages.providers.nuget import _parse_nuget_payload
from solocrawl.core.packages.providers.packagist import _parse_packagist_payload
from solocrawl.core.packages.providers.pub import _parse_pub_payload
from solocrawl.core.packages.providers.pypi import _parse_pypi_payload
from solocrawl.core.packages.providers.rubygems import _parse_rubygems_payload
from solocrawl.core.packages.providers.swift import _parse_tags_payload


def _raises(fn):
    with pytest.raises(PackageNotFoundError):
        fn()


def test_pypi_invalid_payloads() -> None:
    _raises(lambda: _parse_pypi_payload("x", "nope", constraint=None, allow_prerelease=False))
    _raises(lambda: _parse_pypi_payload("x", {}, constraint=None, allow_prerelease=False))


def test_npm_invalid_payloads() -> None:
    _raises(lambda: _parse_npm_payload("x", "nope", constraint=None, allow_prerelease=False))
    _raises(
        lambda: _parse_npm_payload("x", {"versions": {}}, constraint=None, allow_prerelease=False)
    )


def test_packagist_invalid_payloads() -> None:
    _raises(
        lambda: _parse_packagist_payload("v/p", "nope", constraint=None, allow_prerelease=False)
    )
    _raises(
        lambda: _parse_packagist_payload(
            "v/p", {"packages": "x"}, constraint=None, allow_prerelease=False
        )
    )
    _raises(
        lambda: _parse_packagist_payload(
            "v/p", {"packages": {"v/p": []}}, constraint=None, allow_prerelease=False
        )
    )


def test_crates_invalid_payloads() -> None:
    _raises(lambda: _parse_crates_payload("x", "nope", constraint=None, allow_prerelease=False))
    _raises(
        lambda: _parse_crates_payload(
            "x", {"versions": []}, constraint=None, allow_prerelease=False
        )
    )


def test_pub_invalid_payloads() -> None:
    _raises(lambda: _parse_pub_payload("x", "nope", constraint=None, allow_prerelease=False))
    _raises(
        lambda: _parse_pub_payload("x", {"versions": []}, constraint=None, allow_prerelease=False)
    )


def test_rubygems_invalid_payloads() -> None:
    _raises(
        lambda: _parse_rubygems_payload("x", "nope", [], constraint=None, allow_prerelease=False)
    )
    _raises(lambda: _parse_rubygems_payload("x", {}, [], constraint=None, allow_prerelease=False))


def test_nuget_invalid_payloads() -> None:
    _raises(lambda: _parse_nuget_payload("x", "nope", {}, constraint=None, allow_prerelease=False))
    _raises(
        lambda: _parse_nuget_payload(
            "x", {"versions": []}, {}, constraint=None, allow_prerelease=False
        )
    )


def test_maven_invalid_metadata() -> None:
    _raises(
        lambda: _parse_maven_metadata("g:a", "<broken", constraint=None, allow_prerelease=False)
    )
    _raises(
        lambda: _parse_maven_metadata(
            "g:a", "<metadata></metadata>", constraint=None, allow_prerelease=False
        )
    )


def test_golang_empty_versions_and_list_parse() -> None:
    assert _parse_go_version_list("") == []
    assert _parse_go_version_list("v1.0.0\n\nv1.1.0\n") and True
    _raises(lambda: _parse_go_module_payload("m", [], {}, constraint=None, allow_prerelease=False))


def test_swift_invalid_payload() -> None:
    _raises(lambda: _parse_tags_payload("o", "r", "nope", constraint=None, allow_prerelease=False))
