"""URL validation for fetch/scrape operations."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.google",
    }
)

_METADATA_HOST_PATTERN = re.compile(r"^169\.254\.169\.254$")


class FetchUrlError(ValueError):
    """Raised when a URL is not allowed for fetching."""


def validate_fetch_url(url: str, *, allow_internal: bool = False) -> str | None:
    """Return an error message when ``url`` is not allowed, otherwise ``None``."""
    parsed = urlparse(url.strip())

    if parsed.scheme not in {"http", "https"}:
        return "URL must use http or https"

    if not parsed.netloc:
        return "URL must include a host"

    host = _host_from_parsed(parsed)
    if host is None:
        return "URL must include a valid host"

    if allow_internal:
        return None

    if _is_blocked_host(host):
        return f"fetching internal or restricted host is not allowed: {host}"

    return None


def ensure_fetch_url_allowed(url: str, *, allow_internal: bool = False) -> None:
    """Raise ``FetchUrlError`` when ``url`` is not allowed."""
    error = validate_fetch_url(url, allow_internal=allow_internal)
    if error is not None:
        raise FetchUrlError(error)


async def ensure_fetch_url_resolves_allowed(
    url: str,
    *,
    allow_internal: bool = False,
) -> None:
    """Raise ``FetchUrlError`` when ``url`` resolves to a restricted address."""
    ensure_fetch_url_allowed(url, allow_internal=allow_internal)
    if allow_internal:
        return

    parsed = urlparse(url.strip())
    host = _host_from_parsed(parsed)
    if host is None or _is_ip_literal(host):
        return

    addresses = await _resolve_host_addresses(host, parsed.port)
    blocked = [address for address in addresses if _is_blocked_address(address)]
    if blocked:
        blocked_values = ", ".join(str(address) for address in blocked)
        msg = (
            "fetching host that resolves to internal or restricted address is not allowed: "
            f"{host} ({blocked_values})"
        )
        raise FetchUrlError(msg)


def _host_from_parsed(parsed) -> str | None:
    host = parsed.hostname
    if host is None or not host.strip():
        return None
    return host.strip().lower().rstrip(".")


def _is_blocked_host(host: str) -> bool:
    if host in _BLOCKED_HOSTNAMES:
        return True
    if host.endswith(".localhost") or host.endswith(".local"):
        return True
    if _METADATA_HOST_PATTERN.match(host):
        return True

    without_brackets = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        address = ipaddress.ip_address(without_brackets)
    except ValueError:
        return False

    return _is_blocked_address(address)


def _is_ip_literal(host: str) -> bool:
    without_brackets = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        ipaddress.ip_address(without_brackets)
    except ValueError:
        return False
    return True


def _is_blocked_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


async def _resolve_host_addresses(
    host: str,
    port: int | None,
) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    """Resolve host addresses for fetch safety checks."""
    lookup_port = 443 if port is None else port
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            host,
            lookup_port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return ()

    addresses = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        try:
            addresses.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    return tuple(dict.fromkeys(addresses))
