# Feature 19: robots.txt enforcement

## Goal

Actually honour `robots.txt` in the fetch path, so the tool lives up to the "respects robots.txt and
ToS" promise that the README and `project.md` already make.

## Context

Builds on the httpx fetch path (feature 02). Until now the promise was documentation-only; nothing in
the code consulted `robots.txt`. This adds a polite, fail-open check before each fetch. It does not
touch search providers (they call official APIs, not the scrape path).

## Dependencies

- Requires done: 02
- Blocks: -

## Scope

Belongs here: a `robots.txt` fetcher/parser with per-host caching, integration into `fetcher.fetch()`,
a `RobotsDisallowedError` surfaced by the CLI/MCP, and an opt-out config flag. Does not belong:
crawl-delay scheduling, sitemap parsing, or per-provider rules.

## Implementation guidance

- `core/fetch/robots.py`: `is_fetch_allowed(url, *, user_agent, client)` fetches `{scheme}://{netloc}/
  robots.txt` via the **shared** client, parses with `urllib.robotparser.RobotFileParser`, caches the
  parser per host (bounded), and **fails open** — a missing (`>=400`), malformed, or unreachable
  robots.txt allows the fetch. A process-wide lock avoids a thundering herd on first hit.
- Integrate in `fetcher.fetch()` right after URL validation, before acquiring concurrency slots; raise
  `RobotsDisallowedError` when disallowed. The CLI `scrape` and the MCP `scrape` report it as a clean
  error.
- Config: `FetchConfig.respect_robots: bool = True`, env `SOLOCRAWL_RESPECT_ROBOTS` (opt-out). On by
  default.
- Tests reset the robots cache between runs (conftest); fetch tests that assert request counts or run
  network-free disable robots explicitly.

## Acceptance criteria

- [ ] A path disallowed by robots.txt raises `RobotsDisallowedError`; the page is never requested.
- [ ] An allowed path fetches normally.
- [ ] Missing/forbidden/unreachable robots.txt → allowed (fail-open).
- [ ] `SOLOCRAWL_RESPECT_ROBOTS=false` skips the check entirely.
- [ ] robots.txt is fetched once per host (cached).

## How to verify (manual test)

```bash
solocrawl scrape https://www.google.com/search   # disallowed by Google's robots.txt -> clean error
SOLOCRAWL_RESPECT_ROBOTS=false solocrawl scrape https://www.google.com/search
```

## Notes / references

Fail-open is deliberate for a single-user tool; the goal is to respect explicit disallows, not to be
a strict crawler. See `project.md` non-goals.
