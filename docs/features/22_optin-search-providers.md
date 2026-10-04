# Feature 22: Opt-in search providers (GitHub, MDN, SearXNG)

The original Reddit adapter was removed in 2026-10: Reddit requires approved OAuth access,
which does not fit the project's account-free defaults.

## Goal

Add three more opt-in search sources so users can broaden federation with code, web-docs,
and a self-hosted meta-search — all activated via configuration.

## Context

Builds on the search provider interface/registry (04), federation/fusion (06), and the opt-in pattern
from feature 16. These plug in exactly like the existing opt-in providers; no core changes. This
feature also fixes a latent gap: the CLI/MCP search paths previously imported only the three default
providers, so opt-in providers were never registered there — both now import the whole `providers`
package.

## Dependencies

- Requires done: 04, 06, 16
- Blocks: -

## Scope

Belongs here: `github` (REST repo search), `mdn` (MDN search API),
`searxng` (self-hosted JSON API, base URL via `SOLOCRAWL_SEARXNG_URL`). All `zero_config=False`. Does
**not** belong: bring-your-own-key single-source services (Brave/Tavily) — explicitly excluded as
against the project's logic.

## Implementation guidance

- One file per provider under `core/search/providers/`, each `@register(name)` (`searxng` uses
  `required_env_key="SOLOCRAWL_SEARXNG_URL"`), returning `SearchResult`s, failing soft (return `[]`).
  Mirror `hackernews.py`. Register each in `providers/__init__.py`.
- Make `cli/search.py` and `mcp/server.py` import the `providers` package so every registered provider
  (default + opt-in) is selectable when enabled via `SOLOCRAWL_ENABLE_PROVIDERS`.
- URL normalization: MDN `mdn_url` is relative — make it absolute.

## Acceptance criteria

- [ ] Each provider appears in `solocrawl providers` and activates via `SOLOCRAWL_ENABLE_PROVIDERS`.
- [ ] `searxng` activates only when both enabled and `SOLOCRAWL_SEARXNG_URL` is set.
- [ ] Each provider returns normalized `SearchResult`s and degrades to `[]` on error.
- [ ] Fixture/unit tests cover payload parsing, the GitHub fetch path, and opt-in gating.

## How to verify (manual test)

```bash
SOLOCRAWL_ENABLE_PROVIDERS=github,mdn solocrawl search "python asyncio" --limit 5
SOLOCRAWL_ENABLE_PROVIDERS=searxng SOLOCRAWL_SEARXNG_URL=https://searx.example solocrawl search "rust"
```

## Notes / references

- GitHub: `GET /search/repositories?q=` → `items[].{full_name, html_url, description, stargazers_count}`.
- MDN: `GET developer.mozilla.org/api/v1/search?q=` → `documents[].{mdn_url, title, summary, score}`.
- SearXNG: `GET {base}/search?q=&format=json` → `results[].{title, url, content}` (instance must allow
  the JSON format).
