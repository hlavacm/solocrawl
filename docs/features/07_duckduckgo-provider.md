# Feature 07: DuckDuckGo provider (`ddgs`)

## Goal

Add general web search into the default set via the `ddgs` package. This is the only general-web
source in the default and complements the specialized sources (Wikipedia, StackExchange) with "the
whole web".

## Context

`ddgs` is the successor to the frozen `duckduckgo-search` (renamed in 2025). It is the most fragile
part of the default set (scraping-based, occasional rate-limit), which is why it is isolated behind
the `SearchProvider` interface and the occasional fix is expected. See `architecture.md`.

## Dependencies

- Requires done: 04
- Blocks: 09 (default search), 13

## Scope

Belongs here: a DuckDuckGo provider (zero-config) built on `ddgs`, mapping to `SearchResult`, robust
handling of errors and rate-limits. Does not belong here: other providers.

## Implementation guidance

- The `ddgs` dependency. The API is essentially: `from ddgs import DDGS; DDGS().text(query,
  max_results=N)` → a list of results (title, href, body). Verify the current shape - the package evolves.
- **Import robustness** (recommended): try `ddgs`; if absent, fall back to the old
  `duckduckgo_search`; so an install with the other package does not regress. (Leave the details to
  judgment, but count on the old name being deprecated.)
- `ddgs` is synchronous - so it does not block the event loop, run it via `asyncio.to_thread` (or an
  equivalent). This keeps the provider async-compatible on the outside.
- Map to `SearchResult` (`source="duckduckgo"`). Respect the `limit`.
- Rate-limit / errors: log and return an empty/partial result; never raise upward (federation
  handles it, but the provider should degrade cleanly).
- Registration `zero_config=True`.

## Acceptance criteria

- [ ] `DuckDuckGoProvider.search(...)` returns `SearchResult` via `ddgs`, without blocking the event loop.
- [ ] The provider is zero-config and in the default set.
- [ ] Rate-limit/failure does not raise upward; it degrades cleanly.
- [ ] Tests against a **fixture**/mock of `ddgs`: the mapping is correct; the empty/error state is
      handled. (Do not call live DDG in normal CI.)
- [ ] ruff-clean, async on the outside.

## How to verify

```bash
python -c "import asyncio; from solocrawl.core.search.providers.duckduckgo import DuckDuckGoProvider; \
print(asyncio.run(DuckDuckGoProvider().search('python asyncio', limit=3)))"
pytest tests -k duckduckgo
```

## Notes / references

- Package: `ddgs` on PyPI (formerly `duckduckgo-search`, frozen 7/2025). Use `ddgs`.
- Because it is the most fragile provider, isolate `ddgs` specifics into one place, so it is easy to
  fix when DDG changes something.
