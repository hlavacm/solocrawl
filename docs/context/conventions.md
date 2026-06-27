# Conventions

Rules for **how to write the code** so the project is consistent and readable. Where not stated
otherwise, standard modern Python good practices apply.

## Language and version

- **Python 3.14+** (project baseline; `asyncio.TaskGroup`, modern typing). Dependencies such as
  `ddgs` require 3.10+, so 3.14 is well within supported range.
- Full **type hints** everywhere. Public interfaces fully typed.
- Prefer `async/await`. No blocking I/O on the async path (no `requests`, no `time.sleep`).

## Dependencies (keep them minimal and justified)

Core set:
- `httpx` - async HTTP client
- `playwright` - JS fallback (only when rendering is needed)
- `trafilatura` - main-content extraction
- `readability-lxml` - fallback extraction
- `markdownify` - HTML -> markdown (where useful)
- `ddgs` - DuckDuckGo provider
- `packaging` - versions for PyPI/Python semantics
- `mcp` / `fastmcp` - MCP server (FastMCP API)
- optionally a lightweight CLI helper (`typer` or plain `argparse` - agent's call, keep it light)

Dev tooling: `ruff` (lint + format), `pyright` (static type analysis), `pytest` +
`pytest-asyncio`/`anyio` (tests). These three are the mandatory quality gate (see below).

Do not add heavy frameworks (no Django/FastAPI in core; FastAPI at most as an optional example
outside core). Every new dependency must have a clear justification.

## Structure and style

- Package layout per `architecture.md`. Keep modules small and focused.
- Formatting and lint: **ruff** (formatter and linter). Keep the code ruff-clean.
- Naming: `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants.
- Public functions/classes have a short docstring (what it does, not how). For MCP tools the
  docstring matters - **the model sees it**, so it must clearly describe the purpose and parameters.
- Data structures: `@dataclass` (or `pydantic` if the agent deems it appropriate for input
  validation - but don't overload). Normalized output types (`SearchResult`, `PackageInfo`,
  `FetchResult`) are shared in `core/models.py`.

## Errors and robustness

- **Graceful degradation** is the rule, not the exception: one failed provider/source must not bring
  down the whole.
- Log failures (WARNING level) with the provider name and reason; do not raise upward when a sensible
  fallback exists.
- Network operations have **timeouts** and a reasonable number of **retries** (with backoff on
  rate-limits).
- Respect rate-limit signals (HTTP 429/503, `Retry-After`) - especially for StackExchange and DDG.
- Fetch/scrape must preserve SSRF guards: block internal literal hosts, DNS-resolved internal
  addresses, unsafe redirects, and unsafe Playwright final URLs by default.
- Never crash on an "ugly" page - extraction has fallbacks.

## Asynchrony and performance

- One shared `httpx.AsyncClient` per process (lifecycle managed clearly - open/close).
- Concurrency bounded by `asyncio.Semaphore`: global limit + per-domain limit. Values configurable,
  with sensible defaults.
- Playwright: one browser, recycled contexts. Never a browser per request.
- No `gather` over an unbounded number of tasks without a semaphore.

## Configuration

- Configuration via env variables (and/or a simple file). Env naming: prefix `SOLOCRAWL_`
  (e.g. `SOLOCRAWL_PROXY_ENABLED`, `SOLOCRAWL_MAX_CONCURRENCY`, `SOLOCRAWL_ENABLE_PROVIDERS`).
- **All defaults must work with no configuration.** Configuration only turns on extras (opt-in
  providers, proxy) or tunes limits.
- No secret keys in the code. Opt-in providers needing a key take it from env.

## Quality gate (mandatory)

Three checks form a **mandatory gate** that must pass before any task/feature is considered done
(see `agent-workflow.md` - Definition of Done). They are required, not optional:

- **Lint/format**: `ruff check .` and `ruff format --check .` - clean.
- **Static analysis (types)**: `pyright` - no errors.
- **Tests**: `pytest` - green.

Notes on the type checker:
- Use **Pyright** from the CLI. It is the open-source engine behind VS Code's Pylance, so what you
  see in the editor matches what runs in CI. (Pylance itself is an editor-only extension and cannot
  be run from the command line - do not rely on it for the gate.) `mypy` is an acceptable alternative
  if a contributor prefers it, but Pyright is the project default.
- Type-checking mode: **standard** (a reasonable baseline). Strict mode tends to produce noise around
  `Any` from third-party API shapes (scraping responses) - standard is the right balance. Anyone who
  wants more can tighten it in the Pyright config; do not lower it below standard.
- Configure Pyright in `pyproject.toml` (`[tool.pyright]`) or `pyrightconfig.json`, with `pytest`
  and friends on the path. Keep the config in the repo so the gate is reproducible.

## Tests

- **pytest** + `pytest-asyncio` (or `anyio`).
- Providers are tested against **fixtures** (stored HTML/JSON responses in `tests/fixtures/`),
  **not against the live web** - otherwise the tests will be flaky and CI annoying.
- Cover: the version resolver (constraint, pre-release, yanked), RRF fusion + dedup, the extraction
  fallback chain, federation graceful degradation (one provider raises -> the others pass).
- A few optional "smoke" tests against live endpoints may exist, but marked (a marker), so they do
  not run in normal CI.
- Tests are **mandatory** for every feature that adds behavior - not an afterthought. A feature
  without tests for its key behavior is not done.

## Git and commits

- Small, thematic commits. A clear message (Conventional Commits is fine, but not enforced).
- One feature from `docs/features/` ~ one logical batch of commits.

## What NOT to do

- Do not implement the non-goals from `project.md` (no RAG, no own DB of versions, no bypassing ToS).
- Do not add a default provider that requires an account/key.
- Do not make the MCP/CLI shell a carrier of logic - logic belongs in the core.
- Do not over-engineer (no ML ranking, no needless "just-in-case" abstractions).
