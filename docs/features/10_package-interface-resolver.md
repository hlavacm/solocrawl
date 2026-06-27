# Feature 10: Package provider interface + resolver

## Goal

Define the plugin interface for package (version) providers and implement a constraint-aware resolver
that picks the highest suitable version from the available versions (accounting for a constraint,
pre-release, and yanked versions).

## Context

This is the heart of the "agent updates dependencies and must not make up versions" use case. The
resolver is shared logic across ecosystems; providers only supply the list of versions from the
registry (live). See `architecture.md` `core/packages/`.

## Dependencies

- Requires done: 01
- Blocks: 11, 12, 13

## Scope

Belongs here: the `PackageProvider` protocol + registry (mirrors feature 04), the `resolve_latest`
resolver, resolver tests. Does not belong here: concrete registry providers (11).

## Implementation guidance

- The `PackageProvider` protocol:
  - `ecosystem` (`"pypi"`, `"npm"`, `"packagist"`, ...)
  - `async def get_package(self, name: str) -> PackageInfo` - pulls from the registry the list of
    versions + metadata (repo/homepage/changelog URL if present)
- Registry/selector as in search (feature 04) - keep the pattern consistent.
- The resolver (a pure function, well testable):
  ```python
  def resolve_latest(versions, *, constraint=None, allow_prerelease=False) -> str | None
  ```
  - filter pre-release (when `allow_prerelease=False`)
  - filter yanked/withdrawn versions (when this info is available - pass it into the resolver)
  - when there is a `constraint`, return the highest version satisfying it; otherwise the highest stable
- **Versioning semantics differ by ecosystem.** For PyPI/Python use `packaging` (`Version`,
  `SpecifierSet`). For npm/Packagist it is semver with different constraint syntax - design the
  resolver so the semantics can be supplied per-ecosystem (e.g. a strategy/adapter), not hardwired to
  Python only. Start with Python, but keep it extensible.

## Acceptance criteria

- [ ] The `PackageProvider` protocol + registry/selector exist (consistent with the search pattern).
- [ ] `resolve_latest` returns the highest stable version; with a `constraint` the highest satisfying
      one; pre-release and yanked are filtered correctly.
- [ ] The versioning semantics are separated so they can be supplied for npm/Packagist (not just
      Python hardwired).
- [ ] Resolver tests: stable vs. pre-release; constraint (`>=4.2,<5` → highest 4.2.x); yanked
      exclusion; empty input → `None`.
- [ ] ruff-clean, typed.

## How to verify

```bash
pytest tests -k "resolver or package_interface"
```

## Notes

The resolver is the most important tested piece of the whole package layer - this is where it is
decided whether the agent gets the correct version. Covering edge-case versions (rc, post, dev,
yanked) is high priority.
