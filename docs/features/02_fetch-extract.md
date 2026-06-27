# Feature 02: Fetch (httpx) & extract

## Goal

Fetching URLs through a shared async httpx client and converting HTML into clean markdown suitable
for LLM context. This is the heart of scraping and is used by search (to pull content) and by the
`scrape` tool.

## Context

See `architecture.md` sections `core/fetch/` and `core/extract/`. In this feature **httpx only** -
the Playwright fallback comes in feature 14, but design the fetcher interface so the fallback can be
added cleanly (e.g. a `force_browser` parameter and an internal spot where the browser path slots in).

## Dependencies

- Requires done: 01
- Blocks: 03, 05, 11, 14

## Scope

Belongs here: the shared `httpx.AsyncClient` with a clear lifecycle, a `fetch()` function,
HTML→markdown extraction with a fallback chain, handling of encoding/redirect/content-type, a
per-domain + global semaphore. Does not belong here: Playwright (14), proxy (15) - but leave room for
them in the design.

## Implementation guidance

Fetch:
- One shared `httpx.AsyncClient` per process (keep-alive, connection pool). Handle its open/close
  clearly (e.g. a lazy singleton or a lifecycle helper).
- `async def fetch(url, *, force_browser=False) -> FetchResult`:
  - httpx GET with a timeout and reasonable retries (backoff on 429/503, respect `Retry-After`)
  - track the final URL after redirects
  - based on `content-type` decide: HTML → extraction; when something else arrives (PDF/JSON/plain),
    return it reasonably (do not raise; at least plain text or a clear indication of the type)
  - when `force_browser=True`, this is (for now) the spot where Playwright will later kick in - for
    now feel free to return a clear "browser unavailable" or just do httpx; keep the design extensible
- Concurrency: a global `asyncio.Semaphore` + a per-domain limit (from config). Never an unbounded gather.

Extract (`core/extract/`):
- Input HTML → output clean markdown of the main content.
- Fallback chain: `trafilatura` → when it returns almost nothing, `readability-lxml` (+ `markdownify`)
  → last resort plain text from `<body>`. Never crash on an ugly page.
- Handle encoding (httpx usually handles it, but verify) and empty/nonsense outputs (define the
  "almost nothing" threshold that switches to the fallback - you share this threshold with the
  browser fallback in 14).

## Acceptance criteria

- [ ] `fetch(url)` returns a `FetchResult` with markdown content for a normal HTML page.
- [ ] The shared httpx client is not recreated on every request.
- [ ] Redirects, encoding, and non-HTML content-type are handled (it does not crash).
- [ ] Extraction has a working fallback chain; on "empty" extraction it switches to the next method.
- [ ] Concurrency is bounded by a global and a per-domain semaphore (configurable).
- [ ] Timeouts and retry/backoff on rate-limits work.
- [ ] Tests against **fixtures** (stored HTML): extraction returns reasonable markdown; the fallback
      fires on degenerate HTML; URL dedup/normalization if you introduce it here.
- [ ] ruff-clean, fully async, no blocking I/O.

## How to verify

```bash
# via a small ad-hoc script or, later, via the CLI in feature 03
python -c "import asyncio; from solocrawl.core.fetch.fetcher import fetch; \
print(asyncio.run(fetch('https://example.com')).content[:200])"
pytest tests -k "fetch or extract"
```

## Notes

The "almost empty content" threshold is an important shared point with feature 14 (browser
fallback) - design it as one place, not scattered across the code. You can leave the CPU-bound
extraction synchronous; if it turns out to be a bottleneck, the right place is `asyncio.to_thread`
(see architecture), but do not pre-optimize.
