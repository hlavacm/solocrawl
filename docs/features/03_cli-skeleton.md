# Feature 03: CLI skeleton

## Goal

The base of the `solocrawl` CLI with a first working command `scrape`, which calls fetch+extract from
feature 02. After this feature you have the first tangible result: from the terminal you fetch a URL
as markdown.

## Context

The CLI is a thin shell over the core (see `architecture.md`). It serves mainly to quickly try things
without an MCP client - that is key for development and for the project's adoption. Further commands
(`search`, `package`) are added in 09 and 12, so build the CLI extensibly (subcommands).

## Dependencies

- Requires done: 02
- Blocks: 09, 12

## Scope

Belongs here: a CLI entry point, a `scrape <url>` subcommand, reasonable output (markdown to stdout,
optionally a flag to save to a file). Does not belong here: `search` and `package` (just leave room
for them).

## Implementation guidance

- An entry point `solocrawl` (a console script from pyproject). A subcommand structure (`scrape`, later
  `search`, `package`).
- CLI library: `typer` or `argparse` - your call, keep it light and without heavy dependencies.
- `solocrawl scrape <url>`:
  - calls `fetch()` from feature 02, prints markdown to stdout
  - optionally `--out <file>` to save, `--force-browser` (a no-op for now / prepared for 14)
- Handle errors in a user-friendly way (invalid URL, network error) - a clear message, not a traceback.
- The CLI is async-aware (internally runs an event loop); on the outside it is a normal command.

## Acceptance criteria

- [ ] `solocrawl --help` and `solocrawl scrape --help` work and are clear.
- [ ] `solocrawl scrape <url>` fetches the page and prints markdown.
- [ ] `--out` saves to a file; error states give a clear message (not a raw traceback).
- [ ] The subcommand structure is ready for adding `search` and `package`.
- [ ] Test: at least a smoke test that `scrape` against a fixture/local source returns content.
- [ ] ruff-clean.

## How to verify

```bash
solocrawl scrape https://example.com
solocrawl scrape https://example.com --out out.md && head out.md
```

## Notes

Keep the output clean (markdown to stdout, logs/warnings to stderr) so the CLI can be used in a pipeline.
