"""Shared httpx.AsyncClient lifecycle management."""

from __future__ import annotations

import asyncio
import os

import httpx

from solocrawl.config import ConcurrencyConfig

_client: httpx.AsyncClient | None = None
_client_timeout: float | None = None
_client_user_agent: str | None = None
_client_lock = asyncio.Lock()


def default_user_agent() -> str:
    """Return the default HTTP User-Agent for outbound requests."""
    from solocrawl import __version__

    return f"SoloCrawl/{__version__} (+https://github.com/hlavacm/solocrawl; local MCP/CLI tool)"


def resolve_user_agent(user_agent: str | None = None) -> str:
    """Resolve the effective User-Agent from config override or environment."""
    if user_agent is not None and user_agent.strip():
        return user_agent.strip()
    env_value = os.environ.get("SOLOCRAWL_USER_AGENT")
    if env_value is not None and env_value.strip():
        return env_value.strip()
    return default_user_agent()


async def get_client(
    config: ConcurrencyConfig,
    *,
    user_agent: str | None = None,
) -> httpx.AsyncClient:
    """Return the shared httpx client, creating it on first use."""
    global _client, _client_timeout, _client_user_agent
    effective_user_agent = resolve_user_agent(user_agent)
    async with _client_lock:
        timeout = config.timeout_seconds
        if _client is not None and not _client.is_closed:
            if _client_timeout is None:
                return _client
            if _client_timeout == timeout and _client_user_agent == effective_user_agent:
                return _client
        if _client is not None and not _client.is_closed:
            await _client.aclose()
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": effective_user_agent},
            trust_env=False,
        )
        _client_timeout = timeout
        _client_user_agent = effective_user_agent
        return _client


async def close_client() -> None:
    """Close the shared httpx client if it is open."""
    global _client, _client_timeout, _client_user_agent
    async with _client_lock:
        if _client is not None and not _client.is_closed:
            await _client.aclose()
        _client = None
        _client_timeout = None
        _client_user_agent = None


def get_client_for_testing() -> httpx.AsyncClient | None:
    """Return the current shared client (for tests)."""
    return _client


async def set_client_for_testing(client: httpx.AsyncClient | None) -> None:
    """Replace the shared client (for tests)."""
    global _client, _client_timeout, _client_user_agent
    async with _client_lock:
        if _client is not None and not _client.is_closed and _client is not client:
            await _client.aclose()
        _client = client
        _client_timeout = None
        _client_user_agent = None
