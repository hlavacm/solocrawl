# Feature 18: Provider discoverability

## Goal

Let a user (or an LLM) see which search and package providers are registered, which are on by
default vs. opt-in, and what each one needs — without reading the source.

## Context

Builds on the registries from features 04 (search) and 10 (packages), which already expose
`list_registrations()`. This is a thin read-only surface over that data: a CLI subcommand and an MCP
tool. It does not change provider behaviour.

## Dependencies

- Requires done: 04, 09, 10, 12, 13
- Blocks: -

## Scope

Belongs here: a shared core helper that lists registered providers, a `solocrawl providers` CLI
subcommand (text + `--json`), and an MCP `list_providers` tool. Does not belong: enabling/disabling
providers, health checks, or live probing of providers.

## Implementation guidance

- `core/discovery.py` imports both `providers` packages (registration is import-time) and normalizes
  `ProviderRegistration` into a small `ProviderSummary` (kind, name, zero_config, required_env_key,
  ecosystem?). Both shells read from here so listing logic lives in one place (no logic in the shells).
- CLI `cli/providers.py`: `--type {search,package,all}` and `--json`; text output marks each provider
  `default` (zero_config) or `opt-in`, and appends `(requires SOLOCRAWL_…)` when a key is needed.
- MCP `list_providers(provider_type="all")` returns the same information as formatted text.

## Acceptance criteria

- [ ] `solocrawl providers` lists both search and package providers with default/opt-in status.
- [ ] `solocrawl providers --json` emits valid JSON with `search` and `package` arrays.
- [ ] `--type search` / `--type package` filter correctly.
- [ ] The MCP `list_providers` tool is registered and returns the listing.
- [ ] Tests cover the text and JSON shapes against the registered set.

## How to verify (manual test)

```bash
solocrawl providers
solocrawl providers --type package --json
```

## Notes / references

Reuses `core/search/registry.py` and `core/packages/registry.py` `list_registrations()`.
