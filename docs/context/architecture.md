# Architecture

This document describes **how SoloCrawl is assembled and why**. The concrete interfaces are
illustrative - they show intent and shape, not binding code to the last character. The agent has
room to refine them, as long as it preserves the principles below.

## Guiding principles

1. **Core as a library, everything else as a thin shell.** The core (search, fetch, extract,
   packages) must not depend on MCP or the CLI. The MCP server and CLI are just adapters that call
   the core. Reason: testability without an MCP client, and the ability to use the core standalone.
2. **Plugins through a uniform interface + registry.** A new search/package provider = a new file
   that implements the protocol and registers itself. The core knows nothing about concrete providers.
3. **httpx-first, browser as fallback.** The vast majority of pages need no JS. Playwright runs only
   when necessary, because it is an order of magnitude more expensive (memory, CPU, time).
4. **Async everywhere, but bounded.** Fully asynchronous I/O, never unbounded concurrency.
   Concurrency is regulated by semaphores (global + per-domain).
5. **Graceful degradation.** When one source/provider fails, it must not bring down the whole result.
6. **No on-disk state that could go stale.** No caching of package versions into an own DB.
   (A short in-memory cache within a single run is fine.)

## Layers and data flow

```
        MCP shell             CLI
            \                 /
             \               /
              v             v
        ┌───────────────────────┐
        │         CORE          │
        │                       │
        │  search/ (federation) │ --uses--> fetch/  --uses--> proxy/
        │  packages/            │ --uses--> extract/
        │                       │
        └───────────────────────┘
```

### `core/fetch/` - fetching

- Shared `httpx.AsyncClient` (connection pooling, keep-alive) - one per process, not a new one per
  request.
- URL safety is part of the fetch boundary: validate literal hosts, DNS-resolved addresses, each
  redirect target, and Playwright's final browser URL unless `SOLOCRAWL_ALLOW_INTERNAL_URLS=true`.
- `fetcher.fetch(url, force_browser=False)`:
  - tries an httpx GET, sends the result to extraction
  - if the extracted content is suspiciously empty (or `force_browser`), falls back to Playwright
- Playwright: **one** running browser, with recycled `context`s (per task), not a whole browser per
  request. Browser launch is the most expensive operation.
- The proxy layer (see below) and the per-domain + global semaphore plug in here.

### `core/extract/` - HTML -> markdown

- Goal: extract the main content from HTML and convert it to clean markdown suitable for LLM context
  (no noise).
- Strategy with fallback: primarily `trafilatura`; when it returns almost nothing, try
  `readability-lxml`; as a last resort plain text from `<body>`. Never raise just because of an ugly page.
- Watch out for encoding, redirects, and content-type (sometimes a PDF/JSON arrives instead of HTML)
  - handle them.

### `core/proxy/` - optional proxy

- **Disabled** by default. Turned on via configuration.
- `ProxyPool` supports two modes after the Webshare model:
  - a list of concrete proxies (SoloCrawl does the rotation)
  - a single rotating endpoint (the provider does the rotation) - just passed through
- Selection strategy: round-robin / random / sticky-per-domain.
- Health-checking (remove dead proxies) and retry with a different proxy on a block.
- **Handles auth uniformly for httpx and Playwright** - note: Playwright takes proxy auth
  differently (separate `username`/`password` fields in launch options), while httpx accepts
  `user:pass` in the URL. The calling layer must not have to deal with this.

### `core/search/` - federated web search

- `SearchProvider` protocol: `async def search(query, *, limit) -> list[SearchResult]`.
- The registry distinguishes `zero_config` (goes into the default) vs. needs-config (activated via
  configuration).
- `federated_search`: runs the selected providers via `asyncio.gather(..., return_exceptions=True)`,
  logs and skips the ones that fail, merges the rest.
- **Fusion**: results from multiple providers are merged via **RRF (Reciprocal Rank Fusion)** and
  deduplicated by normalized URL. RRF is a few lines, no ML - do not over-engineer.
- Each provider returns a **normalized** `SearchResult`, so fusion is independent of the source.

### `core/packages/` - package version lookup

- `PackageProvider` protocol: determine the versions of a concrete package from an official registry
  (live).
- `resolve_latest(versions, constraint=None, allow_prerelease=False)` - returns the highest version
  satisfying the constraint; filters out pre-release and yanked.
- Default providers: PyPI, npm, Packagist. Each just calls the registry JSON API and parses versions.
- Watch out for the differing semver/versioning semantics across ecosystems (Python `packaging` vs.
  npm semver).

### `mcp/` - MCP shell

- Built on **FastMCP** (the Python MCP SDK), transport **stdio** (LM Studio and others support it).
- Exposes tools, not resources/prompts. At minimum:
  - `web_search(query, limit, sources?)` - federated search
  - `scrape(url)` - fetch + extract to markdown
  - `package_version(name, ecosystem?, constraint?)` - version lookup
- The shell **only calls the core and serializes the output**. No business logic here.
- Tool inputs are bounded for local safety: cap search limit and research depth, and truncate very
  large scrape/research outputs before returning them to the MCP client.

### `cli/` - terminal interface

- The same three operations as MCP, but for a human in a terminal. It serves to quickly try things
  without an MCP client (key for adoption and for development). It too only calls the core.

## Configuration

- A single configuration source (env variables and/or a simple config file) handles: which opt-in
  providers to enable, proxy (on/off + list/endpoint + auth), concurrency limits, timeouts.
- Default values must make sense with no configuration.

## Performance guardrails (do not cross)

- httpx-first, browser only as fallback.
- One shared httpx client; one running browser with recycled contexts.
- Global semaphore on concurrent fetches + per-domain limit (politeness and self-protection).
- CPU-bound parsing (trafilatura) optionally off the event loop (`asyncio.to_thread`) if it turns
  out to be a bottleneck - for local use it may not be needed, but that is the right place.
- No unbounded queues for any link following: a visited-set + a cap on the number of pages.
