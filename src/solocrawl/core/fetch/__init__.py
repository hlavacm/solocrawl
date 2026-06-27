"""HTTP fetching with httpx (Playwright fallback added in a later feature)."""

from solocrawl.core.fetch.fetcher import (
    FetchUrlError,
    RobotsDisallowedError,
    close_browser,
    close_client,
    fetch,
)

__all__ = [
    "FetchUrlError",
    "RobotsDisallowedError",
    "close_browser",
    "close_client",
    "fetch",
]
