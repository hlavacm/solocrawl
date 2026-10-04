"""SoloCrawl MCP server tools and lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastmcp import FastMCP

from solocrawl import __version__ as SOLOCRAWL_VERSION
from solocrawl.config import Config, load_config
from solocrawl.core.discovery import (
    ProviderSummary,
    list_package_providers,
    list_search_providers,
    provider_label,
    provider_status_note,
)
from solocrawl.core.fetch import (
    RobotsDisallowedError,
    close_browser,
    close_client,
    fetch,
)
from solocrawl.core.models import FetchResult, PackageInfo, SearchResult
from solocrawl.core.packages import select_provider_for_ecosystem
from solocrawl.core.packages.providers import (  # noqa: F401
    crates,
    golang,
    maven,
    npm,
    nuget,
    packagist,
    pub,
    pypi,
    rubygems,
    swift,
)
from solocrawl.core.packages.providers.base import PackageNotFoundError
from solocrawl.core.packages.resolver import InvalidConstraintError
from solocrawl.core.proxy import ProxyUnavailableError, redact_proxy_credentials
from solocrawl.core.research import (
    MAX_RESEARCH_DEPTH,
    research_to_markdown,
)
from solocrawl.core.research import (
    research as run_research,
)
from solocrawl.core.search import (
    federated_search,
    select_providers,
)
from solocrawl.core.search import (
    providers as _search_providers,  # noqa: F401  (registers providers)
)

REPO_URL = "https://github.com/hlavacm/solocrawl"
MAX_MCP_SEARCH_LIMIT = 20
MAX_MCP_OUTPUT_CHARS = 100_000


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Keep the shared fetch client and browser alive for the whole server session.

    Cleanup happens once on shutdown, not after every tool call, so connection
    pooling and the recycled Playwright browser survive across invocations.
    """
    try:
        yield
    finally:
        await close_client()
        await close_browser()


mcp = FastMCP(
    name="SoloCrawl",
    version=SOLOCRAWL_VERSION,
    website_url=REPO_URL,
    instructions=(
        "SoloCrawl provides local web search, page scraping to markdown, "
        "and live package version lookup from official registries. "
        "For broad questions that need page content, prefer research over "
        "calling web_search and scrape separately."
    ),
    lifespan=_lifespan,
)


def _format_search_results(results: list[SearchResult]) -> str:
    if not results:
        return "No search results."

    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"{index}. {result.title}",
                f"   URL: {result.url}",
                f"   Source: {result.source}",
            ]
        )
        if result.snippet:
            lines.append(f"   Snippet: {result.snippet}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_scrape_result(result: FetchResult) -> str:
    heading = result.title or result.url or "Scraped page"
    lines = [f"# {heading}"]
    meta = [
        ("URL", result.url if result.url and result.url != heading else None),
        ("Author", result.author),
        ("Date", result.date),
        ("Site", result.site_name),
        ("Language", result.language),
    ]
    meta_lines = [f"> {label}: {value}" for label, value in meta if value]
    if meta_lines:
        lines.append("")
        lines.extend(meta_lines)
    lines.append("")
    header = "\n".join(lines)
    return f"{header}\n{result.content}".strip()


def _format_package_info(info: PackageInfo) -> str:
    lines = [
        f"{info.name} ({info.ecosystem})",
        f"latest: {info.latest}",
    ]
    if info.versions:
        lines.append(f"previous: {', '.join(info.versions)}")
    if info.repository:
        lines.append(f"repository: {info.repository}")
    if info.homepage:
        lines.append(f"homepage: {info.homepage}")
    return "\n".join(lines)


def _truncate_mcp_output(text: str) -> str:
    if len(text) <= MAX_MCP_OUTPUT_CHARS:
        return text
    omitted = len(text) - MAX_MCP_OUTPUT_CHARS
    return f"{text[:MAX_MCP_OUTPUT_CHARS]}\n\n[truncated {omitted} characters]"


def _format_provider_listing(items: list[ProviderSummary]) -> list[str]:
    lines: list[str] = []
    for item in items:
        status, note = provider_status_note(item)
        lines.append(f"  - {provider_label(item)}: {status}{note}")
    return lines


def _providers_for_search(config: Config, sources: list[str] | None) -> list:
    if sources:
        requested = frozenset(source.strip() for source in sources if source.strip())
        narrowed = Config(
            concurrency=config.concurrency,
            proxy=config.proxy,
            browser=config.browser,
            fetch=config.fetch,
            enabled_providers=requested,
        )
        providers = select_providers(narrowed)
        return [provider for provider in providers if provider.name in requested]

    return select_providers(config)


@mcp.tool
async def web_search(
    query: str,
    limit: int = 5,
    sources: list[str] | None = None,
) -> str:
    """Search the web across SoloCrawl's configured providers and return unified results.

    Args:
        query: The search query.
        limit: Maximum number of merged results to return.
        sources: Optional provider names to restrict the search (e.g. wikipedia, duckduckgo).
    """
    config = load_config()
    providers = _providers_for_search(config, sources)
    if not providers:
        return "No search providers are enabled for this request."

    safe_limit = min(max(1, limit), MAX_MCP_SEARCH_LIMIT)
    results = await federated_search(providers, query, limit=safe_limit)
    return _format_search_results(results)


@mcp.tool
async def scrape(url: str) -> str:
    """Fetch a URL and return the main page content as markdown suitable for LLM context.

    Args:
        url: The HTTP or HTTPS URL to scrape.
    """
    try:
        result = await fetch(url)
    except (ValueError, RobotsDisallowedError, ProxyUnavailableError) as exc:
        return f"error: {exc}"
    except httpx.HTTPStatusError as exc:
        return f"error: HTTP {exc.response.status_code} for {url}"
    except httpx.RequestError as exc:
        return f"error: network error: {redact_proxy_credentials(str(exc))}"

    return _truncate_mcp_output(_format_scrape_result(result))


@mcp.tool
async def research(query: str, depth: int = 3) -> str:
    """Search the web, scrape the top results, and return an aggregated cited report.

    Args:
        query: The research query.
        depth: How many top results to scrape and aggregate (default 3).
    """
    safe_depth = min(max(1, depth), MAX_RESEARCH_DEPTH)
    documents = await run_research(query, depth=safe_depth)
    return _truncate_mcp_output(research_to_markdown(query, documents))


@mcp.tool
async def package_version(
    name: str,
    ecosystem: str,
    constraint: str | None = None,
    allow_prerelease: bool = False,
) -> str:
    """Look up the latest or constraint-satisfying version of a package from a registry.

    Args:
        name: Package name (Packagist: vendor/package, Maven: groupId:artifactId, Go: module path,
            Swift: owner/repo on GitHub).
        ecosystem: Registry ecosystem (pypi, npm, packagist, crates, nuget, maven,
            rubygems, go, pub, swift).
        constraint: Optional version constraint such as '>=4.2,<5'.
        allow_prerelease: Whether pre-release versions may be selected.
    """
    config = load_config()
    provider = select_provider_for_ecosystem(ecosystem, config)
    if provider is None:
        return f"No provider available for ecosystem {ecosystem!r}."

    try:
        info = await provider.get_package(
            name,
            constraint=constraint,
            allow_prerelease=allow_prerelease,
        )
    except InvalidConstraintError as exc:
        return f"error: {exc}"
    except PackageNotFoundError as exc:
        return str(exc)

    return _format_package_info(info)


@mcp.tool
async def list_providers(provider_type: str = "all") -> str:
    """List the registered search and package providers (default vs. opt-in).

    Args:
        provider_type: Which providers to list: 'search', 'package', or 'all'.
    """
    lines: list[str] = []
    if provider_type in ("search", "all"):
        lines.append("Search providers:")
        lines.extend(_format_provider_listing(list_search_providers()))
    if provider_type in ("package", "all"):
        if lines:
            lines.append("")
        lines.append("Package providers:")
        lines.extend(_format_provider_listing(list_package_providers()))
    if not lines:
        return f"Unknown provider_type {provider_type!r}; use 'search', 'package', or 'all'."
    return "\n".join(lines)


def create_server() -> FastMCP:
    """Return the configured MCP server instance."""
    return mcp
