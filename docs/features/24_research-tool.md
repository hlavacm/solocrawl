# Feature 24: Research tool (search → scrape → aggregate)

## Goal

A one-shot "research" capability: run a federated search, scrape the top results, and return an
aggregated, cited markdown report — the common LLM workflow, in one call.

## Context

Builds on search federation (06) and the fetch path (02), reusing both. Pure retrieval +
concatenation with citations — **no embeddings or ranking models** (project non-goals). Logic lives in
`core/research.py`; the CLI and MCP are thin shells.

## Dependencies

- Requires done: 06, 02, 09, 13
- Blocks: -

## Scope

Belongs here: `research(query, *, depth)` returning `ResearchDocument`s, a markdown aggregator, a
`solocrawl research` command (`--depth`, `--json`), and an MCP `research` tool. Does not belong:
summarization/LLM calls, vector storage, or re-ranking.

## Implementation guidance

- `core/research.py`: select providers, `federated_search(..., limit=depth)`, take the top `depth`
  hits, `asyncio.gather(fetch(...), return_exceptions=True)`, map to `ResearchDocument` (content or
  error). Inherits robots/concurrency/cache via `fetch`. `research_to_markdown` builds the cited
  report.
- CLI `research.py` (mirror `search.py`); MCP `research` tool returns the markdown. Import the
  `providers` package so federation has the configured providers.

## Acceptance criteria

- [ ] `solocrawl research "<q>" --depth 3` returns an aggregated report citing each source URL.
- [ ] Per-source fetch failures degrade gracefully (noted, not fatal).
- [ ] `--json` emits the structured documents.
- [ ] The MCP `research` tool is registered.
- [ ] Tests cover aggregation, error handling, and the markdown/JSON output.

## How to verify (manual test)

```bash
solocrawl research "python asyncio semaphore" --depth 3
solocrawl research "rust ownership" --depth 2 --json
```

## Notes / references

`depth` controls both how many results are scraped and the search breadth.
