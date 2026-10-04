<p align="center">
  <img src="assets/icon/solocrawl.png" alt="SoloCrawl logo" width="128">
</p>

<h1 align="center">SoloCrawl</h1>

<p align="center">
  <strong>Web search, scraping, and live package-version lookup —<br>
  for your terminal, your code, and your local LLM.</strong><br>
  No accounts. No API keys. No cloud.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.14%2B-blue.svg" alt="Python 3.14+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/MCP-ready-8A2BE2.svg" alt="MCP ready">
  <img src="https://img.shields.io/badge/API%20keys-none%20required-success.svg" alt="No API keys required">
</p>

---

SoloCrawl is a small, self-hosted, fully async Python tool that does three things well: it **searches
the web** across many sources at once, **scrapes pages into clean markdown** that's ready for an LLM,
and **looks up the latest package version** from official registries. It runs on your machine, for
free, and works the moment you install it — nothing to sign up for, no keys to paste.

It's built for individual developers and people tinkering with local LLMs. Use it as an **MCP server**
(LM Studio, Claude Desktop, OpenCode, …), straight from the **CLI**, or as a **Python library**.

## ✨ Highlights

| | |
|---|---|
| 🔌 **Zero config** | Search, scrape, and package lookup all work out of the box — no accounts, no keys. |
| 🔎 **Federated search** | Queries 11 possible sources, merges them with Reciprocal Rank Fusion and de-duplicates URLs into one clean ranking. |
| 📄 **Smart scraping** | HTML → tidy markdown via `trafilatura`/`readability`, with a Playwright browser fallback for JS-heavy pages — used only when it's actually needed. |
| 📦 **Live package versions** | 10 ecosystems (PyPI, npm, crates.io, Maven, Go, …) resolved live from official registries — never a stale local DB. |
| 🤖 **MCP-native** | Drops straight into local LLM tooling as a stdio MCP server with five ready tools. |
| ⚡ **Fully async, bounded** | One shared HTTP client, one recycled browser, global + per-domain concurrency limits. Fast without hammering anyone. |
| 🧩 **Hackable** | Add a search or package provider as a single self-registering file — the core stays untouched. |
| 🔒 **Safe by default** | Blocks localhost/private/cloud-metadata targets and honours `robots.txt`. |

## 🚀 Quick start

The recommended way to install SoloCrawl is **pipx** — it drops the `solocrawl` and `solocrawl-mcp`
commands onto your PATH in their own isolated environment, so you can run them from anywhere without
juggling a virtualenv:

```bash
git clone https://github.com/hlavacm/solocrawl.git
pipx install ./solocrawl     # or an absolute path: pipx install /path/to/solocrawl
```

> Already on PyPI? Then it's just `pipx install solocrawl` — no checkout needed.

That's it — now run the three core commands from any directory:

```bash
# Scrape a page to markdown
solocrawl scrape https://example.com

# Federated web search (Wikipedia + DuckDuckGo + StackExchange by default)
solocrawl search "python asyncio semaphore" --limit 5

# Live package version lookup
solocrawl package requests --ecosystem pypi
```

### Updating

```bash
# Installed from PyPI:
pipx upgrade solocrawl

# Installed from a local checkout — pull the latest changes, then reinstall:
cd /path/to/solocrawl && git pull && pipx install --force .   # alias: pipx reinstall solocrawl
```

After upgrading, restart your MCP client (LM Studio, Cursor, Claude Desktop, …) so it picks up the new
`solocrawl-mcp` binary — your `mcp.json` needs no changes as long as it points at `solocrawl-mcp` on
your PATH.

## What you can do

### 🔎 Search the web

One query, many sources, a single merged ranking — no single provider deciding everything for you.

```bash
solocrawl search "python asyncio semaphore" --limit 5

# Pick exactly which sources to hit, and get machine-readable output
solocrawl search "django orm" --sources wikipedia,stackexchange --json
```

### 📄 Scrape a page to clean markdown

Turn any URL into LLM-ready markdown with page metadata (title, author, date, …) as front-matter.

```bash
solocrawl scrape https://example.com

# Save to a file, or force the browser for a JS-rendered page
solocrawl scrape https://example.com --out page.md
solocrawl scrape https://example.com --force-browser
```

### 📦 Look up package versions

The current version — and the one matching your constraint — straight from the official registry.

```bash
solocrawl package react --ecosystem npm --constraint ">=18,<19"
solocrawl package monolog/monolog --ecosystem packagist --json
solocrawl package some-lib --ecosystem pypi --allow-prerelease
```

### 🧪 Research in one shot

The classic LLM workflow — search, scrape the top hits, and get back one aggregated, **cited** report.

```bash
solocrawl research "python asyncio semaphore" --depth 3
```

### 🗂️ Batch-scrape many URLs

Fetch a whole list at once under the same bounded concurrency; `--out-dir` writes one file per URL.

```bash
solocrawl batch https://example.com https://www.python.org --out-dir /tmp/scrape
solocrawl batch --from-file urls.txt --out-dir /tmp/scrape
```

### …and see what's available

```bash
# List every registered provider (search + package), default vs. opt-in
solocrawl providers
```

## 🤖 Use it with your local LLM (MCP)

This is where SoloCrawl really shines — give your local model (LM Studio, OpenCode, Claude Desktop, …)
the ability to search, scrape, and check versions. The `pipx install` from the
[Quick start](#-quick-start) already put `solocrawl-mcp` on your PATH, so all that's left is pointing
your MCP client at it.

**LM Studio / Claude Desktop** — ready-to-use config at **[examples/mcp.json](examples/mcp.json)**.
Drop it into your client's MCP settings (`mcp.json`):

```json
{
  "mcpServers": {
    "solocrawl": {
      "command": "solocrawl-mcp",
      "args": [],
      "env": {
        "SOLOCRAWL_LOG_LEVEL": "INFO",
        "SOLOCRAWL_LOG_FILE": "~/.local/state/solocrawl/mcp.log"
      }
    }
  }
}
```

**OpenCode** — uses a different config format. Copy
**[examples/opencode.jsonc](examples/opencode.jsonc)** into `~/.config/opencode/opencode.jsonc`
(global) or `opencode.jsonc` in your project root. OpenCode expects `type: "local"`, `command` as an
array, and `environment` instead of `env`.

If your MCP client doesn't inherit your shell `PATH`, replace `"solocrawl-mcp"` with the full path
from `which solocrawl-mcp` (typically `~/.local/bin/solocrawl-mcp` after `pipx install`). Logs go to
stderr (visible in LM Studio Developer Logs) and optionally to `SOLOCRAWL_LOG_FILE`.

The server exposes **five tools**:

- `web_search(query, limit=5, sources=None)` — federated search across enabled providers
- `scrape(url)` — fetch and extract markdown (with page metadata) from a URL
- `research(query, depth=3)` — search, scrape the top results, and return an aggregated cited report
- `package_version(name, ecosystem, constraint=None, allow_prerelease=False)` — live registry lookup
- `list_providers(provider_type="all")` — list registered search/package providers (default vs. opt-in)

To check the active version and command path:

```bash
pipx list | grep solocrawl
which solocrawl-mcp
```

> **Working from a local clone?** A `pipx`-installed `solocrawl-mcp` is a *snapshot* — editing the
> repo does **not** update the command on your `PATH`, so your MCP client keeps running the old
> code. After changing the source, refresh it with `pipx install --force .` (or install once with
> `pipx install --editable .` so future edits are picked up automatically).

## 🐍 Use it from Python

```python
import asyncio

from solocrawl.config import load_config
from solocrawl.core.search import federated_search, select_providers
from solocrawl.core.search.providers import duckduckgo, stackexchange, wikipedia  # noqa: F401


async def main() -> None:
    providers = select_providers(load_config())
    results = await federated_search(providers, "asyncio python", limit=3)
    for result in results:
        print(result.title, result.url)


asyncio.run(main())
```

See [examples/library_search.py](examples/library_search.py) for a runnable example.

## Search providers

**Default (zero-config, always enabled):**

| Provider | Source |
|----------|--------|
| `wikipedia` | MediaWiki API |
| `duckduckgo` | `ddgs` package |
| `stackexchange` | Stack Exchange API (Stack Overflow) |

**Opt-in** (enable with `SOLOCRAWL_ENABLE_PROVIDERS`):

| Provider | Source |
|----------|--------|
| `wikidata` | Wikidata entity search |
| `hackernews` | Hacker News (Algolia) |
| `arxiv` | arXiv Atom API |
| `pubmed` | PubMed/NCBI E-utilities |
| `github` | GitHub repository search |
| `mdn` | MDN Web Docs search |
| `searxng` | Self-hosted SearXNG (set `SOLOCRAWL_SEARXNG_URL`) |

The Reddit adapter was removed because Reddit [requires approved OAuth access](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki).
Legacy `SOLOCRAWL_ENABLE_PROVIDERS=reddit` settings no longer activate a provider.

```bash
SOLOCRAWL_ENABLE_PROVIDERS=arxiv,hackernews solocrawl search "transformer attention" --limit 6
SOLOCRAWL_ENABLE_PROVIDERS=github,mdn solocrawl search "fetch api" --limit 6
```

## Package registries

Default ecosystems: **PyPI**, **npm**, **Packagist**, **crates.io**, **NuGet**, **Maven Central**,
**RubyGems**, **Go modules**, **pub.dev**, **Swift**. Versions are always fetched live from official
registries — SoloCrawl does not maintain its own version database. Swift packages have no central
registry, so versions come from the repository's git tags (`owner/repo` on GitHub).

```bash
solocrawl package serde --ecosystem crates
solocrawl package Newtonsoft.Json --ecosystem nuget
solocrawl package org.junit.jupiter:junit-jupiter --ecosystem maven
solocrawl package github.com/gorilla/mux --ecosystem go
solocrawl package apple/swift-argument-parser --ecosystem swift
```

### Version constraints

PyPI uses PEP 440 (`>=1.2,<2`, `~=1.4`, `==1.2.*`). Other registries use a common SemVer
range subset: comparators, exact versions, `^`, `~`, partials and wildcards, whitespace/comma AND,
`||` OR and hyphen ranges (`1.2 - 1.3` includes the whole 1.3 series). SemVer prereleases such as
`canary.1` retain their ordering and bounds; enable them with `--allow-prerelease`.
Native Maven/NuGet interval notation and RubyGems `~>` are not supported and are rejected clearly.
SoloCrawl does not claim to implement each registry's complete native range grammar. Maven, NuGet
and RubyGems retain numeric/standard prerelease ordering through `packaging`, including four-part
numeric releases; SemVer ecosystems use `semver`.
PyPI releases without files or with all files yanked are excluded; mixed yanking keeps the release
available. Swift follows GitHub tag pagination, and Go module paths use the proxy's case escaping.

## Optional extras

```bash
# Browser fallback for JS-heavy pages (Playwright)
pip install -e ".[browser]"
playwright install chromium

solocrawl scrape https://example.com --force-browser

# Install everything
pip install -e ".[all]"
```

## ⚙️ Configuration

**All defaults work with no configuration.** Everything below is optional and uses the `SOLOCRAWL_`
prefix. For local development, copy `.env.dist` to `.env` and uncomment what you need — SoloCrawl
loads `.env` automatically via [python-dotenv](https://pypi.org/project/python-dotenv/), and existing
shell environment variables take precedence.

<details>
<summary>Environment variables</summary>

| Variable | Default | Purpose |
|----------|---------|---------|
| `SOLOCRAWL_ENABLE_PROVIDERS` | _(empty)_ | Comma-separated opt-in provider names |
| `SOLOCRAWL_SEARXNG_URL` | _(empty)_ | Base URL of a self-hosted SearXNG instance (enables the `searxng` provider) |
| `SOLOCRAWL_RESPECT_ROBOTS` | `true` | Honour `robots.txt` on scrape (fail-open); set `false` to skip |
| `SOLOCRAWL_CACHE_TTL_SECONDS` | `0` | In-memory fetch cache TTL in seconds (`0` = disabled) |
| `SOLOCRAWL_MAX_CONCURRENCY` | `10` | Global fetch concurrency limit |
| `SOLOCRAWL_PER_DOMAIN_LIMIT` | `2` | Per-domain concurrency limit |
| `SOLOCRAWL_TIMEOUT_SECONDS` | `30` | Per-request timeout in seconds |
| `SOLOCRAWL_MAX_RETRIES` | `3` | Retries on network errors / rate limits |
| `SOLOCRAWL_MAX_RESPONSE_BYTES` | `10485760` | Cap on fetched response body size (10 MiB); larger bodies are truncated |
| `SOLOCRAWL_PROXY_ENABLED` | `false` | Enable optional proxy layer |
| `SOLOCRAWL_PROXY_MODE` | `list` | Proxy mode: `list` (rotate a pool) or `endpoint` (single rotating endpoint) |
| `SOLOCRAWL_PROXY_LIST` | _(empty)_ | Comma-separated proxy URLs |
| `SOLOCRAWL_PROXY_ENDPOINT` | _(empty)_ | Single rotating proxy endpoint |
| `SOLOCRAWL_PROXY_USERNAME` | _(empty)_ | Proxy auth username |
| `SOLOCRAWL_PROXY_PASSWORD` | _(empty)_ | Proxy auth password |
| `SOLOCRAWL_ALLOW_INTERNAL_URLS` | `false` | Allow scraping localhost/private IPs (dev only) |
| `SOLOCRAWL_USER_AGENT` | _(SoloCrawl default)_ | Override HTTP User-Agent for API requests |
| `SOLOCRAWL_BROWSER_ALLOWED` | `true` | Allow Playwright fallback when installed |
| `SOLOCRAWL_LOG_LEVEL` | `WARNING` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SOLOCRAWL_LOG_FILE` | _(empty)_ | Optional log file path (also logs to stderr) |

</details>

Concurrency, response-size limits and timeout must be positive; retries and cache TTL must be
non-negative. Timeout must be finite. Invalid settings report the environment-variable name rather
than hanging a request. Catch proxy exhaustion in library code with
`from solocrawl.core.proxy import ProxyUnavailableError`. Enabling a proxy requires valid HTTP(S) endpoints. A depleted proxy pool
raises `ProxyUnavailableError`; it never silently switches to a direct connection. Robots checks
and browser requests use the selected proxy too.

## 🔒 Security note on URL fetching

By default SoloCrawl refuses to fetch localhost, link-local, private, reserved, and
cloud-metadata addresses. It checks literal hosts, DNS-resolved A/AAAA records, HTTP redirect
targets, and every routed browser request (including frames and subresources). Browser redirects
are fetched one hop at a time, service workers and WebSockets are blocked, and the final browser URL
is checked. SoloCrawl is still a single-user local tool, not a
hostile-multi-tenant proxy — do not expose it to untrusted network callers.
`SOLOCRAWL_ALLOW_INTERNAL_URLS=true` disables these internal-target checks entirely (intended for
trusted local development only).

DNS checks and the eventual connection use separate resolution steps, so they do not eliminate
DNS rebinding or a proxy resolving a hostname differently. Use network-level egress controls when
strong isolation is needed. `robots.txt` is enforced on every HTTP redirect destination and browser
request, with the existing fail-open policy for unavailable or redirected robots files.

Browser main-page redirects retain their final URL. Redirected iframe, script and XHR subrequests
are aborted after validating the destination: replaying them through Playwright's fetch API would
change browser origin/relative-URL semantics and could forward authorization or POST bodies. This
restriction may prevent some pages from rendering completely. Ordinary HTTP redirects still work.

## 🧩 Extending it

The whole point of the plugin layout is that adding a source is a single self-registering file — the
core never changes. To add a search provider:

1. Create `src/solocrawl/core/search/providers/myprovider.py` implementing `SearchProvider`.
2. Register with `@register("myprovider", zero_config=True, configurable=True)` or as opt-in.
   Configurable providers accept `__init__(self, *, config: Config | None = None)`; selectors pass
   the supplied configuration. Legacy zero-argument providers keep `configurable=False` (the default).
3. Import the module in `src/solocrawl/core/search/providers/__init__.py` so registration runs.
4. Add fixture-based tests in `tests/`.

The same pattern applies to package providers under `src/solocrawl/core/packages/providers/`.

## Development

Work from a checkout in a virtualenv with an editable install — this also drops the `solocrawl` and
`solocrawl-mcp` scripts into `.venv/bin/`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

The MCP server uses FastMCP 4 / MCP SDK v2. Its five tools and stdio wire format stay the same;
client-side Python protocol fields use snake_case (`input_schema`, `is_error`).
See the [official migration guide](https://gofastmcp.com/getting-started/upgrading/from-fastmcp-3).

Then run the quality gate:

```bash
ruff check . && ruff format --check .
pyright
pytest

# …or all in one line:
ruff check . && pyright && pytest
```

For guided verification and shareable JSON feedback, see [docs/verification.md](docs/verification.md):

```bash
python scripts/verify_project.py --mode offline
python scripts/verify_project.py --mode browser
python scripts/verify_project.py --mode all
```

Live tests are optional. The normal suite excludes live and real-browser tests; CI runs local
Chromium fixtures separately. Release checks are listed in
[docs/release/CHECKLIST.md](docs/release/CHECKLIST.md).

## Ethics and terms of use

SoloCrawl is built for individual developers and local LLM tooling. It respects the robots.txt and
terms of service of target sites — `scrape` consults `robots.txt` and refuses disallowed URLs by
default (fail-open on errors; opt out with `SOLOCRAWL_RESPECT_ROBOTS=false`). The proxy and scraping
features are **not** intended to bypass site rules, captchas, or anti-bot systems. Use responsibly and
stay within legitimate access patterns.

## License

MIT — see [LICENSE](LICENSE).
