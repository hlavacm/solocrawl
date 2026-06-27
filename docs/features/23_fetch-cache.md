# Feature 23: Lightweight fetch TTL cache

## Goal

Avoid re-fetching the same URL repeatedly within a process, reducing live calls and being gentler on
target sites — opt-in, off by default.

## Context

Builds on the fetch path (feature 02). In-process only, matching the "one shared client per process"
model. Mainly benefits the long-lived MCP server and multi-URL operations (research/batch, features
24–25).

## Dependencies

- Requires done: 02
- Blocks: 24, 25 (they benefit but do not require it)

## Scope

Belongs here: an in-memory TTL cache keyed by URL, integrated into `fetcher.fetch()`, with a config
TTL (default 0 = disabled). Does **not** belong: disk/sqlite persistence, HTTP cache-header semantics,
or caching `force_browser` renders.

## Implementation guidance

- `core/fetch/cache.py`: `cache_get`/`cache_set(url, result, ttl)`/`reset_cache()`. Bounded size
  (clear when full). Use `time.monotonic` for expiry.
- `fetcher.fetch()`: when `cache_ttl_seconds > 0` and not `force_browser`, return a cache hit before
  robots/slots; on a miss, store successful results (`status > 0`). Extract the slot-bound body into a
  helper so caching wraps it cleanly.
- Config: `FetchConfig.cache_ttl_seconds: int = 0`, env `SOLOCRAWL_CACHE_TTL_SECONDS`.
- conftest resets the cache between tests.

## Acceptance criteria

- [ ] With a positive TTL, a second fetch of the same URL is served from cache (no second network hit).
- [ ] With TTL 0 (default), nothing is cached.
- [ ] Entries expire after the TTL.

## How to verify (manual test)

```bash
SOLOCRAWL_CACHE_TTL_SECONDS=300 solocrawl scrape https://example.com   # second call within 5 min is cached
```

## Notes / references

In-process cache; it resets when the CLI exits. The MCP server (long-lived) benefits most.
