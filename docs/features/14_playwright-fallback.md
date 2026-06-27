# Feature 14: Playwright fallback

## Goal

Augment fetch with rendering of JS-heavy pages via Playwright, which kicks in only when httpx is not
enough (empty/insufficient content). Extends scraping coverage without sacrificing performance on
normal pages.

## Context

The architecture is httpx-first, browser as fallback (see `architecture.md`). Feature 02 left room in
the fetcher for the browser path and a shared "almost empty content" threshold - here that is filled
in. Playwright is expensive (memory/CPU/time), which is why it runs minimally.

## Dependencies

- Requires done: 02 (fetch + emptiness threshold)
- Blocks: 15 (proxy concerns the browser too)

## Scope

Belongs here: a Playwright pool (one browser, recycled contexts), wiring to the fallback in the
fetcher, configuration of browser availability. Does not belong here: proxy (15).

## Implementation guidance

- `core/fetch/browser.py`: **one** running browser (lazy launch), recycled `context`s per task. Never
  a browser per request - launch is the most expensive operation. Correct cleanup on shutdown.
- Wiring in `fetcher.fetch`:
  - when the httpx extraction returns "almost nothing" (the same threshold as 02) or
    `force_browser=True`, fall back to the browser: render the page, wait for a reasonable state
    (network idle / a selector), take the content, run it through the same extraction (extraction is
    shared, the browser only supplies better HTML).
- Respect the global + per-domain semaphore for the browser path too (the browser is more expensive;
  optionally give it its own, lower concurrency limit).
- Configuration: whether Playwright is available/allowed (from feature 01). When it is not installed,
  fetch must still work in httpx-only mode (graceful) - the browser is an extension, not a hard
  dependency.
- Put Playwright in an optional extra (`pip install solocrawl[browser]` + `playwright install`).

## Acceptance criteria

- [ ] A JS-heavy page where httpx returns empty goes through the Playwright fallback and returns content.
- [ ] A normal static page **does not launch** the browser (verifiable - e.g. a counter/log).
- [ ] One shared browser, recycled contexts; correct cleanup.
- [ ] Without Playwright installed, fetch still works in httpx-only mode (no hard crash).
- [ ] The browser concurrency is bounded.
- [ ] Tests: the fallback fires on "empty" httpx extraction (can be mocked); httpx-only mode without a
      browser works.
- [ ] ruff-clean, async.

## How to verify

```bash
pip install -e ".[browser]" && playwright install chromium
solocrawl scrape <some-JS-heavy-URL> --force-browser
```

## Notes

The key is that the fallback really is a fallback - the vast majority of fetches must stay on httpx.
Keep the emptiness threshold in one place (shared with feature 02), so the behavior is tuned centrally.
