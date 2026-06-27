# Feature 06: Federation + RRF fusion

## Goal

Run multiple search providers in parallel, handle failures of individual sources (graceful
degradation), and merge their results into a single ranking using RRF (Reciprocal Rank Fusion) with
deduplication by URL.

## Context

This is what makes SoloCrawl more than just a wrapper of a single source - a unified result from
multiple sources at once (see `architecture.md` `core/search/`). After feature 05 you have one
provider; here you add orchestration over an arbitrary set of providers.

## Dependencies

- Requires done: 04 (interface), 05 (at least one provider to test with)
- Blocks: 09 (CLI search), 13 (MCP web_search)

## Scope

Belongs here: `federated_search`, RRF fusion, URL dedup/normalization, graceful degradation. Does not
belong here: additional concrete providers (7,8,16), CLI/MCP wiring.

## Implementation guidance

- `async def federated_search(providers, query, *, limit) -> list[SearchResult]`:
  - run `provider.search(...)` for all selected providers via `asyncio.gather(...,
    return_exceptions=True)` (or `TaskGroup` with error handling)
  - a provider that raises is **logged (WARNING) and skipped** - never bring down the whole
  - merge the results via RRF
- RRF: for each result, compute the score `sum(1 / (k + rank))` over the lists where it appears
  (`k` a constant, typically ~60). No ML, a few lines.
- Dedup: normalize the URL (scheme, trailing slash, optionally stripping tracking parameters) and
  merge duplicates across sources; in the merged result keep info about how many/which sources a
  result came from (it can raise its score).
- Trim the output to `limit`.

## Acceptance criteria

- [ ] `federated_search` runs multiple providers in parallel and returns a merged, ranked list.
- [ ] When one provider raises, the other results are returned (graceful degradation).
- [ ] RRF fusion is implemented; dedup by normalized URL works.
- [ ] Tests: two dummy providers → correct merge and order; one failing provider → results from the
      other still come through; duplicate URLs are merged.
- [ ] ruff-clean, async, typed.

## How to verify

```bash
pytest tests -k "federation or rrf or fusion"
```

## Notes

Deliberately do not over-engineer RRF - it is an intentionally simple and robust way to merge rankings
from multiple sources. More advanced ranking is out of scope for phase 1.
