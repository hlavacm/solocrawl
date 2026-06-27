# Feature 09: CLI `search`

## Goal

Add a `search` command to the CLI that runs a federated web search across the default providers and
prints the unified results. Milestone: working web search from the terminal across three sources.

## Context

Connects federation (06) with the default providers (05, 07, 08) into a user command. The CLI remains
a thin shell over the core (see `architecture.md`).

## Dependencies

- Requires done: 03 (CLI skeleton), 06 (federation), 05+07+08 (default providers)
- Blocks: -

## Scope

Belongs here: a `search` subcommand, provider selection via the selector, output format. Does not
belong here: new providers, MCP.

## Implementation guidance

- `solocrawl search "<query>"`:
  - via the selector (feature 04) takes the active providers (default = Wikipedia + DDG +
    StackExchange)
  - calls `federated_search`
  - prints the results readably: rank, title, url, source(s), a short snippet
- Flags (your call): `--limit N`, `--sources a,b` (restrict/choose providers), `--json` (a
  machine-readable output - useful for scripting and for comparison with the MCP output).
- Data output to stdout, logs to stderr.

## Acceptance criteria

- [ ] `solocrawl search "rust async runtime" --limit 5` returns merged results from the default providers.
- [ ] `--sources` allows choosing a subset of providers; `--json` gives a machine output.
- [ ] When one provider fails, the command still returns results from the others (graceful
      degradation is visible at the CLI level too).
- [ ] A smoke test of the command (against mocks/fixtures, not live in CI).
- [ ] ruff-clean.

## How to verify

```bash
solocrawl search "python asyncio semaphore" --limit 5
solocrawl search "django orm" --sources wikipedia,stackexchange --json
```

## Notes

This is a good place to manually verify that federation + three real sources give a meaningful unified
result (live, outside CI). It is the project's first "wow" milestone.
