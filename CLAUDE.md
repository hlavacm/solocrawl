# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SoloCrawl is a self-hosted, fully async Python tool for **web search**, **scraping**, and
**package-version lookup**, exposed three ways: an **MCP server** (FastMCP, stdio), a **CLI**, and a
**library**. Zero accounts/API keys for the default setup. Requires **Python 3.14+**.

## Spec-driven workflow

This project is built from specs in `docs/`, **not** ad hoc. Before non-trivial work:

- Read `docs/context/` — `project.md` (scope + **non-goals**), `architecture.md` (how it's
  assembled + performance guardrails), `conventions.md` (how to write code), `agent-workflow.md`
  (Definition of Done).
- Features live in `docs/features/NN_*.md` and are built **one at a time** in the order of
  `docs/features/ROADMAP.md`. Each feature must leave the project runnable.
- Stick to the **intent** of a spec, not its literal wording; verify real-world API shapes when they
  differ. Never cross the non-goals in `project.md` (no RAG/embeddings, no own version DB, no
  ToS/robots bypass, no paid-key default providers, no logic in the MCP/CLI shells).

## Quality gate (mandatory — must all pass before a feature is "done")

```bash
ruff check . && ruff format --check .   # lint + format, must be clean
pyright                                  # standard mode, no errors (this is the gate, not Pylance)
pytest                                   # green; runs against fixtures, never the live web
```

Run a single test: `pytest tests/test_federation.py::test_name -q`

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ".[browser]" for Playwright fallback, ".[all]" for everything
playwright install chromium      # only if using the browser fallback
```

Run locally: `solocrawl scrape <url>` / `solocrawl search "<q>"` / `solocrawl package <name> --ecosystem <eco>`.
MCP entry point is `solocrawl-mcp` (stdio).

## Architecture

**Core as a library; MCP and CLI are thin adapters.** `core/` must never import from `mcp/` or
`cli/`. The shells only call core and serialize output — no business logic there.

```
mcp/ (FastMCP, stdio)   cli/ (argparse)
            \           /
             v         v
      core/  search/ ── fetch/ ── proxy/
             packages/  extract/
             models.py (shared SearchResult / FetchResult / PackageInfo)
```

- `core/fetch/` — one shared `httpx.AsyncClient` per process. `fetcher.fetch(url, force_browser=False)`
  does httpx-first, falling back to Playwright **only** when extraction comes back suspiciously empty
  or when forced. One browser, recycled contexts. Bounded by global + per-domain semaphores
  (`concurrency.py`). URL validation guards literal hosts, DNS-resolved internal addresses, HTTP
  redirects, and Playwright's final browser URL.
- `core/extract/` — HTML→markdown for LLM context. Fallback chain: `trafilatura` →
  `readability-lxml` → plain `<body>` text. Never raises on an ugly page.
- `core/search/` — `SearchProvider` protocol (`async search(query, *, limit)`). `federation.py` runs
  selected providers via `gather(return_exceptions=True)`, logs+skips failures (graceful
  degradation), then `fusion.py` merges via **RRF (Reciprocal Rank Fusion)** + URL-normalized dedup.
- `core/packages/` — `PackageProvider` protocol. `resolver.resolve_latest(versions, constraint,
  allow_prerelease)` picks the highest version satisfying a constraint, filtering pre-release/yanked.
  Versions are always fetched **live** from official registries.
- `core/proxy/` — optional, off by default. `ProxyPool` supports a proxy list (we rotate) or a
  single rotating endpoint (passthrough); unifies auth across httpx (URL) and Playwright
  (launch options).

## Plugin pattern (search + package providers)

Both subsystems use a decorator registry (`registry.py`). To add a provider:

1. New file under `core/{search,packages}/providers/myprovider.py` implementing the protocol.
2. Decorate with `@register("name", zero_config=True)` (search) or
   `@register("name", ecosystem="...", zero_config=True)` (packages). `zero_config=True` puts it in
   the default set; otherwise it's opt-in via `SOLOCRAWL_ENABLE_PROVIDERS`. Use `required_env_key`
   for bring-your-own-key providers.
3. **Import the module in `providers/__init__.py`** so the decorator runs (registration is import-time).
4. Add fixture-based tests.

Tests call `clear_registry()` to isolate — registries are module-global.

## Conventions that bite

- Full type hints; `from __future__ import annotations` at top of modules. Async everywhere — **no
  blocking I/O** on the async path (`requests`, `time.sleep` are out). Line length 100.
- Normalized output types live only in `core/models.py` (dataclasses).
- Config is env-only with the `SOLOCRAWL_` prefix; **all defaults must work with no config**.
  `.env` is auto-loaded via python-dotenv (`config.init_env()`); shell env takes precedence. Copy
  `.env.dist` → `.env` for local dev.
- MCP-facing tools must stay bounded: search limit is capped, research depth is capped, and large
  scrape/research responses are truncated before returning to the client.
- Providers are tested against stored fixtures in `tests/fixtures/`, never the live web.
  `tests/conftest.py` auto-resets fetch/concurrency/browser state between tests.
- Keep dependencies minimal and justified; don't over-engineer (no ML ranking, no speculative
  abstractions).
