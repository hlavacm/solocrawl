# Feature 05: Wikipedia provider

## Goal

The first concrete search provider - Wikipedia via the official MediaWiki/REST API. It is chosen
first because it is the most stable (an official JSON API, no key), so it also serves as a reference
implementation of `SearchProvider` for the others.

## Context

See `architecture.md` `core/search/`. The provider implements the interface from feature 04 and
returns normalized `SearchResult`. No scraping - a clean API.

## Dependencies

- Requires done: 04 (interface), 02 (fetch - the shared httpx client can be reused)
- Blocks: 06 (federation needs at least one provider end-to-end)

## Scope

Belongs here: the Wikipedia provider (zero-config), mapping the response to `SearchResult`, tests
against fixtures. Does not belong here: other providers, federation.

## Implementation guidance

- Use the official Wikipedia/MediaWiki API (the search endpoint returns relevant pages; the REST
  summary can also be used for a snippet). Return `title`, `url` (to the article), `snippet` (a short
  extract), `source="wikipedia"`.
- The language/wiki can be configurable (default `en`), but do not over-engineer - the default is enough.
- For the HTTP call use the shared httpx client from feature 02 (do not open your own).
- Respect the `limit`. Handle empty results and errors (return an empty list / log, do not raise
  upward - it will be called in federation with graceful degradation).
- Registration via the registry as `zero_config=True`.

## Acceptance criteria

- [ ] `WikipediaProvider.search("python", limit=5)` returns a list of `SearchResult` with filled fields.
- [ ] The provider is registered as zero-config and the selector includes it in the default.
- [ ] An error/empty result does not raise upward.
- [ ] Tests against a **fixture** (a stored API response): the mapping to `SearchResult` is correct;
      an empty response → an empty list.
- [ ] ruff-clean, async, typed.

## How to verify

```bash
python -c "import asyncio; from solocrawl.core.search.providers.wikipedia import WikipediaProvider; \
print(asyncio.run(WikipediaProvider().search('python', limit=3)))"
pytest tests -k wikipedia
```

## Notes / references

The MediaWiki Action API and the Wikimedia REST API are stable and key-free. Verify the current shape
of the endpoint and fields if you have tools - reality takes precedence over this description.
