"""Tests for the Swift package provider (GitHub tags backed)."""

from __future__ import annotations

import json

import httpx
import pytest

from solocrawl.config import Config
from solocrawl.core.fetch.client import set_client_for_testing
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.providers.swift import (
    SwiftProvider,
    _parse_identifier,
    _parse_tags_payload,
)


def test_parse_tags_picks_latest_stable(read_fixture) -> None:
    payload = json.loads(read_fixture("swift_tags.json"))
    info = _parse_tags_payload(
        "apple",
        "swift-argument-parser",
        payload,
        constraint=None,
        allow_prerelease=False,
    )

    assert info.latest == "1.3.0"  # 1.4.0-beta.1 is a pre-release and excluded
    assert info.repository == "https://github.com/apple/swift-argument-parser"
    assert "1.2.3" in info.versions
    assert "nightly" not in info.versions


def test_parse_tags_honours_constraint(read_fixture) -> None:
    payload = json.loads(read_fixture("swift_tags.json"))
    info = _parse_tags_payload(
        "apple",
        "swift-argument-parser",
        payload,
        constraint=">=1.2,<1.3",
        allow_prerelease=False,
    )

    assert info.latest == "1.2.3"


def test_parse_tags_allows_prerelease(read_fixture) -> None:
    payload = json.loads(read_fixture("swift_tags.json"))
    info = _parse_tags_payload(
        "apple",
        "swift-argument-parser",
        payload,
        constraint=None,
        allow_prerelease=True,
    )

    assert info.latest == "1.4.0-beta.1"


def test_parse_tags_without_versions_raises() -> None:
    tags = [{"name": "nightly"}]
    with pytest.raises(PackageNotFoundError):
        _parse_tags_payload("o", "r", tags, constraint=None, allow_prerelease=False)


@pytest.mark.parametrize(
    "identifier",
    [
        "apple/swift-argument-parser",
        "https://github.com/apple/swift-argument-parser",
        "github.com/apple/swift-argument-parser.git",
    ],
)
def test_parse_identifier_variants(identifier: str) -> None:
    assert _parse_identifier(identifier) == ("apple", "swift-argument-parser")


def test_parse_identifier_rejects_bad_name() -> None:
    with pytest.raises(PackageNotFoundError):
        _parse_identifier("just-a-name")


async def test_provider_fetches_tags(read_fixture) -> None:
    fixture = read_fixture("swift_tags.json")
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json=json.loads(fixture), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = SwiftProvider(config=Config())
    info = await provider.get_package("apple/swift-argument-parser")

    assert info.latest == "1.3.0"
    assert "api.github.com/repos/apple/swift-argument-parser/tags" in requests[0]
    await client.aclose()


async def test_provider_404_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await set_client_for_testing(client)

    provider = SwiftProvider(config=Config())
    with pytest.raises(PackageNotFoundError):
        await provider.get_package("apple/does-not-exist")
    await client.aclose()
