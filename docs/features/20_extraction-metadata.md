# Feature 20: Extraction metadata

## Goal

Surface page metadata (title, author, date, language, site name) alongside the scraped markdown so an
LLM gets richer, better-grounded context.

## Context

Builds on the extraction chain (feature 02). trafilatura already parses this metadata; until now only
its markdown output was used. This adds a small metadata extractor and threads the values through
`FetchResult` into the CLI and MCP output.

## Dependencies

- Requires done: 02
- Blocks: -

## Scope

Belongs here: a `extract_metadata()` returning a `PageMetadata`, new optional `FetchResult` fields,
YAML front-matter in the CLI `scrape` output, and a metadata header in the MCP `scrape` output. Does
not belong: schema.org/JSON-LD deep parsing, language detection models, or changing the markdown body.

## Implementation guidance

- `core/extract/extractor.py`: `PageMetadata` dataclass + `extract_metadata(html, *, url=None)` using
  `trafilatura.extract_metadata`; never raises, returns empty `PageMetadata()` on failure/empty input.
- `core/models.py`: `FetchResult` gains `title/author/date/language/site_name` (all `str | None = None`).
- `fetcher.py`: populate metadata for HTML results in both the httpx and browser paths.
- CLI `scrape`: prepend YAML front-matter **only when** at least one metadata field is present (plain
  pages keep their current output). MCP `scrape`: title heading + `> Field: value` lines.

## Acceptance criteria

- [ ] A page with metadata yields front-matter containing the present fields (CLI) and a metadata
      header (MCP).
- [ ] A page without metadata produces no empty fields and does not crash (no front-matter added).
- [ ] `extract_metadata` never raises and returns `PageMetadata()` for empty/garbage input.

## How to verify (manual test)

```bash
solocrawl scrape https://en.wikipedia.org/wiki/Python_(programming_language) | head
```

## Notes / references

trafilatura 2.x `extract_metadata` returns a `Document` with `title/author/date/sitename/language`.
