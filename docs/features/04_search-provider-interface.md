# Feature 04: Search provider interface + registry

## Goal

Define the plugin interface for web search providers and a registry that distinguishes zero-config
providers (go into the default) from opt-in providers (activated via configuration).

## Context

This is the backbone of the web search plugin architecture (see `architecture.md` section
`core/search/`). The core knows nothing about concrete providers - it knows only the protocol and
the registry. Thanks to that, a new provider is added as a new file without touching the core.

## Dependencies

- Requires done: 01
- Blocks: 05, 06, 07, 08, 16

## Scope

Belongs here: the `SearchProvider` protocol, a registration mechanism, a selector (which providers to
enable based on zero-config + configuration). Does not belong here: concrete providers (5,7,8,16) or
federation (6).

## Implementation guidance

- `SearchProvider` (Protocol or ABC):
  - an attribute `name` (a stable identifier, appears in `SearchResult.source`)
  - an attribute/flag `zero_config: bool`
  - `async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]`
- Registry: a decorator or a registration function that records the provider under its name and notes
  whether it is zero-config. Illustratively:
  ```python
  @register("wikipedia", zero_config=True)
  class WikipediaProvider: ...
  ```
- Selector: a function that, based on the config (feature 01), returns the provider instances to be
  used = all zero-config + the opt-in ones the user enabled. Opt-in providers requiring a key are
  activated only when the key is in env.
- Bear in mind that providers must be importable/discoverable so they register (import of the
  `providers/` submodule). Choose a simple mechanism (an explicit import in `__init__`, or a light
  discovery) - do not over-engineer.

## Acceptance criteria

- [ ] A `SearchProvider` protocol exists with `name`, `zero_config`, `search()`.
- [ ] The registry allows registering a provider and getting the list of available ones.
- [ ] The selector returns the correct set of providers based on the config (zero-config always;
      opt-in per settings; key-required only with a key).
- [ ] A test with a **dummy provider**: registration works, the selector respects zero-config vs.
      opt-in.
- [ ] ruff-clean, typed.

## How to verify

```bash
pytest tests -k "registry or provider_selection"
```

## Notes

The same pattern (protocol + registry + selector) is repeated in feature 10 for package providers.
Keep it simple and consistent so it can be "mirrored" for packages.
