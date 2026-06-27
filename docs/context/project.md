# Project: SoloCrawl

## What it is

SoloCrawl is a **self-hosted, fully asynchronous tool for web search, scraping, and package-version
lookup**, written in Python. It is primarily exposed as an **MCP server** so that local LLM tools
(LM Studio, OpenCode, Claude Desktop) can use it. Alongside that it works as a standalone library
and as a CLI.

It is built as a hobby / reference open-source project - the code should be clean, readable, and
well structured, because it also serves as an example of how such a tool is built.

## Why it exists (motivation)

Ready-made web search services for local AI tooling (Tavily, Exa, Brave, Firecrawl cloud) either
require an account and impose monthly limits, or are paid outright. SoloCrawl aims to deliver the
same value **for free and locally**, built on sources that are either free official APIs or can be
scraped easily and legally.

## Main goals

1. **Works immediately after cloning.** `git clone`, install dependencies, run - with no need to
   create accounts, obtain API keys, or run extra infrastructure (no mandatory Docker, no mandatory
   external service).
2. **Three core capabilities:**
   - **web search** - a federated query across multiple sources at once, unified result
   - **scrape** - fetch a URL and convert it to clean markdown suitable for LLM context
   - **package version lookup** - determine the current (and constraint-satisfying) version of a package
3. **Plugin architecture** - search providers and package providers are added as plugins without
   touching the core.
4. **Performance and full asynchrony** - the entire I/O stack is async, with bounded concurrency.
5. **Usable three ways** - as an MCP server, as a library, as a CLI.

## Scope - phase 1 (what is being built now)

**Web search providers:**
- Default (zero-config, enabled by themselves, require nothing): **DuckDuckGo** (via the `ddgs`
  package), **Wikipedia** (MediaWiki API), **StackExchange** (Stack Overflow and sibling sites).
- Opt-in (prepared but disabled by default, activated via configuration): **Wikidata**,
  **Hacker News** (Algolia API), **arXiv**, **PubMed/NCBI**.

**Package version providers:**
- Default (zero-config): **PyPI** (Python), **npm** (JS), **Packagist** (PHP), **crates** (Rust),
  **NuGet** (.NET), **Maven** (Java), **RubyGems** (Ruby), **Go** modules, **pub** (Dart), **Swift**
  (GitHub tags).
- Constraint-aware: can return the highest version satisfying a constraint (e.g. `>=4.2,<5`),
  filters out pre-release and yanked versions, also returns a few previous versions and a repo link.

**Shared foundation:**
- core as a library + thin MCP shell + CLI
- httpx-first fetch with a Playwright fallback for JS-heavy pages
- bounded concurrency (global + per-domain limit)
- proxy layer (optional, disabled by default), designed after the Webshare model

## Non-goals (intentionally out of scope, do not implement)

- **It is not documentation RAG / Context7.** No embeddings, no vector index, no building a
  knowledge base over documentation. (Possible future extension or sibling project, not now.)
- **It does not hold its own database of packages/versions.** Versions are always looked up live
  from official registries, so the data is true at the moment of the query.
- **It does not fight anti-bot systems, captcha farms, or do massive crawling.** The target user is
  an individual / developer, not a scaled scraping operation.
- **It does not bypass ToS and robots.txt.** The tool must respect the rules of target sites; the
  README states this. Scraping of general-web sources is limited to what is legitimate (DDG via
  `ddgs`), not bypassing Google/Bing.
- **It does not implement paid single-source services as defaults.** Brave/Tavily/Exa/Google may
  exist only as opt-in "bring your own key" plugins, not in the default set.

## Target audience

Developers and enthusiasts around local LLMs, RAG, and dev tooling. The choice of sources reflects
this (Stack Overflow, arXiv, package registries), as does the emphasis on being able to try the tool
from the CLI within half a minute.

## Definition of success

A stranger clones the repo, and within a few minutes has working web search and package lookup in
LM Studio (or from the CLI), with no account or key - and the code is clean enough that they can add
their own provider by following it.
