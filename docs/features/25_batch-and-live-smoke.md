# Feature 25: Batch scrape + live smoke tests

## Goal

Scrape several URLs in one command (using the existing bounded concurrency), and add live smoke tests
behind a marker so the end-to-end paths can be checked against the real web on demand.

## Context

Builds on the fetch path (02) and concurrency (02). Batch is a thin CLI over `fetch` + `asyncio.gather`.
The live smoke tests close the checklist item "live smoke tests only under a marker".

## Dependencies

- Requires done: 02, 03, 09, 11
- Blocks: -

## Scope

Belongs here: a `solocrawl batch` command (URLs as args or `--from-file`, optional `--out-dir`), and
`tests/test_smoke_live.py` marked `@pytest.mark.live` (deselected by default). Does **not** belong:
resume/retry state, crawling/link-following, or per-URL scheduling.

## Implementation guidance

- `cli/batch.py`: collect URLs (args + file, skipping blanks/`#`), `asyncio.gather(fetch(...),
  return_exceptions=True)`, then print each (`# url` + content) or write `DIR/<sha>.md`. Report
  per-URL failures to stderr; exit non-zero if any failed or no URLs. Keep it simple — no resume.
- pytest: register a `live` marker and set `addopts = -m 'not live'` so the default gate skips live
  tests; run them with `pytest -m live`.
- Docs: update README (new commands/providers/env flags) and the release CHECKLIST live-smoke item.

## Acceptance criteria

- [ ] `solocrawl batch <u1> <u2>` prints both; `--out-dir` writes one file per URL.
- [ ] `--from-file` reads URLs (comments/blank lines skipped).
- [ ] A failing URL is reported and yields a non-zero exit, without aborting the others.
- [ ] `pytest` (default) stays green and skips live tests; `pytest -m live` is defined.

## How to verify (manual test)

```bash
solocrawl batch https://example.com https://www.python.org --out-dir /tmp/scrape
pytest -m live   # on a networked machine
```

## Notes / references

Live tests are intentionally tolerant (paths work, not exact content).
