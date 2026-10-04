"""HTTP fetching with httpx and content extraction."""

from __future__ import annotations

import asyncio
import json
import logging
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from solocrawl.config import Config, load_config
from solocrawl.core.extract.extractor import extract_html, extract_metadata
from solocrawl.core.extract.threshold import is_content_too_short
from solocrawl.core.fetch.browser import close_browser, fetch_rendered_html
from solocrawl.core.fetch.cache import cache_get, cache_set
from solocrawl.core.fetch.client import close_client, get_client, resolve_user_agent
from solocrawl.core.fetch.concurrency import acquire_fetch_slots
from solocrawl.core.fetch.robots import RobotsDisallowedError, is_fetch_allowed
from solocrawl.core.fetch.url_validation import (
    FetchUrlError,
    ensure_fetch_url_allowed,
    ensure_fetch_url_resolves_allowed,
)
from solocrawl.core.models import FetchResult
from solocrawl.core.proxy import get_proxy_pool

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_BROWSER_UNAVAILABLE_MESSAGE = (
    "Browser-based fetching is not available. "
    "Install solocrawl[browser] and run playwright install."
)

_RETRYABLE_STATUS_CODES = frozenset({429, 503})
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 20


async def fetch(
    url: str,
    *,
    force_browser: bool = False,
    config: Config | None = None,
) -> FetchResult:
    """Fetch a URL and return extracted markdown (or raw content for non-HTML)."""
    cfg = load_config() if config is None else config
    ensure_fetch_url_allowed(url, allow_internal=cfg.fetch.allow_internal_urls)

    use_cache = cfg.fetch.cache_ttl_seconds > 0 and not force_browser
    cache_key = (url, cfg)
    if use_cache:
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    result = await _fetch_within_slots(url, cfg, force_browser=force_browser)

    if use_cache and result.status > 0:
        cache_set(cache_key, result, cfg.fetch.cache_ttl_seconds)

    return result


async def _fetch_within_slots(url: str, cfg: Config, *, force_browser: bool) -> FetchResult:
    async with acquire_fetch_slots(url, cfg.concurrency):
        await ensure_fetch_url_resolves_allowed(
            url,
            allow_internal=cfg.fetch.allow_internal_urls,
        )

        if force_browser:
            browser_result = await _fetch_with_browser(url, cfg)
            if browser_result is not None:
                return browser_result
            if not cfg.browser.allowed:
                return FetchResult(
                    url=url,
                    content="Browser fetching is disabled by configuration.",
                    content_type="text/plain",
                    status=0,
                    browser_used=False,
                )
            return FetchResult(
                url=url,
                content=_BROWSER_UNAVAILABLE_MESSAGE,
                content_type="text/plain",
                status=0,
                browser_used=False,
            )

        client = await get_client(cfg.concurrency, user_agent=cfg.fetch.user_agent)
        response, body = await _request_with_retries(client, url, cfg)
        result = _build_fetch_result(response, body)

        if is_content_too_short(result.content):
            browser_result = await _fetch_with_browser(url, cfg)
            if browser_result is not None:
                return browser_result

        return result


class _RetryNeeded(Exception):
    """Internal signal that a request should be retried after ``delay`` seconds."""

    def __init__(self, delay: float) -> None:
        super().__init__()
        self.delay = delay


async def _request_with_retries(
    client: httpx.AsyncClient,
    url: str,
    config: Config,
) -> tuple[httpx.Response, bytes]:
    last_error: Exception | None = None
    attempts = config.concurrency.max_retries + 1
    pool = get_proxy_pool(config.proxy)
    domain = urlparse(url).netloc
    request_headers = {"User-Agent": resolve_user_agent(config.fetch.user_agent)}

    for attempt in range(attempts):
        endpoint = pool.select(domain=domain) if pool.enabled else None
        proxy_url = endpoint.httpx_proxy_url() if endpoint is not None else None
        try:
            return await _attempt_request(
                client,
                url,
                config,
                proxy_url=proxy_url,
                request_headers=request_headers,
                attempt=attempt,
            )
        except _RetryNeeded as retry:
            if endpoint is not None:
                pool.mark_unhealthy(endpoint)
            await asyncio.sleep(retry.delay)
            continue
        except httpx.RequestError as exc:
            if endpoint is not None:
                pool.mark_unhealthy(endpoint)
            last_error = exc
            if attempt < config.concurrency.max_retries:
                await asyncio.sleep(_backoff_seconds(attempt))
                continue
            raise

    if last_error is not None:
        raise last_error
    msg = f"failed to fetch {url} after {attempts} attempts"
    raise RuntimeError(msg)


async def _attempt_request(
    client: httpx.AsyncClient,
    url: str,
    config: Config,
    *,
    proxy_url: str | None,
    request_headers: dict[str, str],
    attempt: int,
) -> tuple[httpx.Response, bytes]:
    if proxy_url is not None:
        async with httpx.AsyncClient(
            timeout=client.timeout,
            follow_redirects=True,
            proxy=proxy_url,
            headers=request_headers,
            trust_env=False,
        ) as proxy_client:
            return await _send_and_read(proxy_client, url, config, attempt=attempt)
    return await _send_and_read(client, url, config, attempt=attempt)


async def _send_and_read(
    client: httpx.AsyncClient,
    url: str,
    config: Config,
    *,
    attempt: int,
) -> tuple[httpx.Response, bytes]:
    current_url = url
    for redirect_count in range(_MAX_REDIRECTS + 1):
        await ensure_fetch_url_resolves_allowed(
            current_url,
            allow_internal=config.fetch.allow_internal_urls,
        )
        if config.fetch.respect_robots and not await is_fetch_allowed(
            current_url,
            user_agent=resolve_user_agent(config.fetch.user_agent),
            client=client,
        ):
            raise RobotsDisallowedError(f"robots.txt disallows fetching {current_url}")
        request = client.build_request("GET", current_url)
        response = await client.send(request, stream=True, follow_redirects=False)
        try:
            if (
                response.status_code in _RETRYABLE_STATUS_CODES
                and attempt < config.concurrency.max_retries
            ):
                delay = _retry_delay_seconds(response, attempt)
                logger.warning(
                    "retryable status %s for %s; retrying in %.1fs (attempt %s/%s)",
                    response.status_code,
                    current_url,
                    delay,
                    attempt + 1,
                    config.concurrency.max_retries,
                )
                raise _RetryNeeded(delay)

            if response.status_code in _REDIRECT_STATUS_CODES and "Location" in response.headers:
                if redirect_count >= _MAX_REDIRECTS:
                    msg = f"too many redirects while fetching {url}"
                    raise httpx.TooManyRedirects(msg, request=request)
                location = response.headers["Location"]
                next_url = str(response.url.join(location))
                await ensure_fetch_url_resolves_allowed(
                    next_url,
                    allow_internal=config.fetch.allow_internal_urls,
                )
                current_url = next_url
                continue

            await _ensure_response_url_allowed(response, config)
            response.raise_for_status()
            body = await _read_body_capped(
                response,
                current_url,
                config.fetch.max_response_bytes,
            )
            return response, body
        finally:
            if not response.is_closed:
                await response.aclose()

    msg = f"too many redirects while fetching {url}"
    raise httpx.TooManyRedirects(msg)


async def _read_body_capped(response: httpx.Response, url: str, limit: int) -> bytes:
    """Read the response body, stopping once ``limit`` bytes have been buffered."""
    chunks = bytearray()
    truncated = False
    async for chunk in response.aiter_bytes():
        remaining = limit - len(chunks)
        if remaining <= 0:
            truncated = True
            break
        if len(chunk) > remaining:
            chunks.extend(chunk[:remaining])
            truncated = True
            break
        chunks.extend(chunk)

    if truncated:
        logger.warning("response body for %s exceeded %d bytes; truncating", url, limit)
    return bytes(chunks)


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        parsed = _parse_retry_after(retry_after)
        if parsed is not None:
            return parsed
    return _backoff_seconds(attempt)


def _parse_retry_after(value: str) -> float | None:
    stripped = value.strip()
    if stripped.isdigit():
        return float(stripped)
    try:
        retry_at = parsedate_to_datetime(stripped)
    except TypeError, ValueError, OverflowError:
        return None
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0.0, (retry_at - now).total_seconds())


def _backoff_seconds(attempt: int) -> float:
    return float(2**attempt)


async def _ensure_response_url_allowed(response: httpx.Response, config: Config) -> None:
    await ensure_fetch_url_resolves_allowed(
        str(response.url),
        allow_internal=config.fetch.allow_internal_urls,
    )


async def _fetch_with_browser(url: str, config: Config) -> FetchResult | None:
    rendered = await fetch_rendered_html(
        url,
        concurrency=config.concurrency,
        browser_config=config.browser,
        proxy_config=config.proxy,
        allow_internal_urls=config.fetch.allow_internal_urls,
        fetch_config=config.fetch,
    )
    if rendered is None:
        return None

    content = extract_html(rendered.html, url=rendered.url)
    if is_content_too_short(content):
        return None

    meta = extract_metadata(rendered.html, url=rendered.url)
    return FetchResult(
        url=rendered.url,
        content=content,
        content_type="text/html",
        status=200,
        browser_used=True,
        title=meta.title,
        author=meta.author,
        date=meta.date,
        language=meta.language,
        site_name=meta.site_name,
    )


def _build_fetch_result(response: httpx.Response, body: bytes) -> FetchResult:
    final_url = str(response.url)
    content_type = _normalize_content_type(response.headers.get("content-type", ""))
    text = _decode_body(body, response)

    if _is_html_content_type(content_type):
        content = extract_html(text, url=final_url)
        meta = extract_metadata(text, url=final_url)
        return FetchResult(
            url=final_url,
            content=content,
            content_type=content_type,
            status=response.status_code,
            browser_used=False,
            title=meta.title,
            author=meta.author,
            date=meta.date,
            language=meta.language,
            site_name=meta.site_name,
        )

    content = _content_for_non_html(text, content_type, byte_count=len(body))
    return FetchResult(
        url=final_url,
        content=content,
        content_type=content_type,
        status=response.status_code,
        browser_used=False,
    )


def _decode_body(body: bytes, response: httpx.Response) -> str:
    encoding = response.charset_encoding or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _normalize_content_type(content_type: str) -> str:
    return content_type.split(";", maxsplit=1)[0].strip().lower()


def _is_html_content_type(content_type: str) -> bool:
    if not content_type:
        return False
    return (
        content_type in {"text/html", "application/xhtml+xml"}
        or content_type.endswith("+html")
        or "html" in content_type
    )


def _content_for_non_html(body: str, content_type: str, *, byte_count: int) -> str:
    if content_type == "application/json":
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return body
        return json.dumps(parsed, indent=2, ensure_ascii=False)

    if content_type == "application/pdf":
        return f"[Binary PDF content, {byte_count} bytes]"

    if content_type.startswith("text/") or not content_type:
        return body

    return f"[Unsupported content type: {content_type}]\n{body[:2000]}"


__all__ = [
    "FetchUrlError",
    "RobotsDisallowedError",
    "close_browser",
    "close_client",
    "fetch",
]
