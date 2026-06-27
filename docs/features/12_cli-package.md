# Feature 12: CLI `package`

## Goal

Add a `package` command to the CLI for determining the current (and constraint-satisfying) version of
a package. Milestone: working package version lookup from the terminal.

## Context

Connects the package providers (11) and the resolver (10) into a user command. The CLI is a thin shell
over the core.

## Dependencies

- Requires done: 03 (CLI), 11 (providers)
- Blocks: -

## Scope

Belongs here: a `package` subcommand, ecosystem selection, constraint, output format. Does not belong
here: new ecosystems.

## Implementation guidance

- `solocrawl package <name>`:
  - `--ecosystem pypi|npm|packagist` (required, or with auto-detection from context; default is your
    call - it is reasonable to require the ecosystem explicitly so packages are not confused across
    registries)
  - `--constraint ">=4.2,<5"` (optional) → returns the highest satisfying version
  - `--allow-prerelease` (optional)
  - `--json` for machine output
- Print: the resolved `latest`, optionally a few previous versions, repo/homepage URL.
- Nonexistent package / error → a clear message.

## Acceptance criteria

- [ ] `solocrawl package django --ecosystem pypi` prints the current version and metadata.
- [ ] `--constraint` returns the highest satisfying version (not just the absolutely newest).
- [ ] `--json` gives machine output; a nonexistent package gives a clean message.
- [ ] A smoke test of the command (against fixtures/mocks in CI).
- [ ] ruff-clean.

## How to verify

```bash
solocrawl package requests --ecosystem pypi
solocrawl package react --ecosystem npm --constraint ">=18,<19"
solocrawl package monolog/monolog --ecosystem packagist --json
```

## Notes

This is exactly the use case the package layer exists for: when bumping dependencies, the agent
supplies `--constraint` from an existing requirement and gets a safe target version.
