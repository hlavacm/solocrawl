# Feature 15: Proxy layer (Webshare model)

## Goal

An optional proxy layer for fetch (httpx and Playwright), designed after the Webshare model (the free
tier of ~10 rotating IPs as a reference). Disabled by default; turned on via configuration.

## Context

See `architecture.md` `core/proxy/`. Proxy is an extension for scraping, not mandatory complexity -
most users will run without it. The important thing is uniform auth handling for httpx and Playwright,
which pass credentials differently.

## Dependencies

- Requires done: 02 (httpx fetch), 14 (browser fetch)
- Blocks: -

## Scope

Belongs here: `ProxyPool`, two modes (list vs. rotating endpoint), selection strategy, health-check,
retry with a different proxy, uniform auth for httpx and Playwright. Does not belong here: a concrete
integration with a paid provider's API (just a general model that covers Webshare and others).

## Implementation guidance

- `ProxyPool` with two modes (after Webshare):
  - **a list of concrete proxies** - SoloCrawl drives the rotation
  - **a single rotating endpoint** - the provider drives the rotation, SoloCrawl just passes through
- Selection strategy: round-robin / random / **sticky-per-domain** (the same proxy for the same
  domain within a run - useful and polite).
- **Health-checking**: remove dead/unresponsive proxies; periodically or lazily on failure.
- **Retry with a different proxy** on a block/error (up to a reasonable number of attempts).
- **Uniform auth - important:** httpx accepts `user:pass` directly in the proxy URL; Playwright takes
  proxy auth differently (separate `username`/`password` fields in launch/context options). `ProxyPool`
  must supply each layer the right shape, so the caller (fetcher/browser) does not have to deal with
  the difference.
- Configuration (feature 01): `enabled` (default false), mode, proxy source (list/endpoint/env),
  strategy. Disabled = behavior as before.
- Interaction with the per-domain limit: with proxy rotation a block is per IP, so the per-domain
  concurrency can effectively be raised - but keep this configurable and conservative, do not handle
  it aggressively (scope and politeness).

## Acceptance criteria

- [ ] `ProxyPool` supports both modes (list and rotating endpoint).
- [ ] The selection strategy works (at least round-robin + sticky-per-domain).
- [ ] Health-check removes nonfunctional proxies; retry tries a different proxy on failure.
- [ ] Auth works **for both httpx and Playwright** (uniformly via the pool).
- [ ] Disabled by default - with no configuration the fetch behavior does not change.
- [ ] Tests: selection/rotation, removal of a dead proxy, retry; (proxies can be mocked).
- [ ] ruff-clean, async.

## How to verify

```bash
# with SOLOCRAWL_PROXY_* variables set (e.g. the Webshare free tier)
SOLOCRAWL_PROXY_ENABLED=1 solocrawl scrape https://example.com
```

## Notes / references

- The Webshare free tier (~10 rotating IPs) is a good reference model for testing both modes.
- The README/CHECKLIST should emphasize respect for robots.txt and ToS - proxy must not serve to
  bypass the rules of target sites (see non-goals in `project.md`).
