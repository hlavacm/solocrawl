# Feature 11: PyPI / npm / Packagist providers

## Goal

Implement three default package providers that live-fetch versions and metadata from official
registries: PyPI (Python), npm (JS), Packagist (PHP).

## Context

The providers fill `PackageInfo` for the resolver from feature 10. No own DB - always a live query
(see non-goals in `project.md`). See `architecture.md` `core/packages/`.

## Dependencies

- Requires done: 10 (interface + resolver), 02 (shared httpx client)
- Blocks: 12, 13

## Scope

Belongs here: three providers (PyPI, npm, Packagist), mapping registry responses to `PackageInfo`,
wiring to the resolver, tests against fixtures. Does not belong here: further ecosystems (crates,
RubyGems, Go).

> **Status (post phase 1):** the additional ecosystems were subsequently implemented following the
> same provider/registry pattern and are now part of the default set: crates.io, NuGet, Maven
> Central, RubyGems, Go modules, and pub.dev (see `core/packages/providers/`). npm/Packagist
> constraint resolution uses a native semver parser (`^`, `~`, `x`-ranges, `||`), not PEP 440.

## Implementation guidance

- **PyPI**: `https://pypi.org/pypi/{name}/json`. Contains `info` (incl. the latest version,
  repo/homepage URL) and `releases` (all versions; individual files carry a `yanked` flag). Pass the
  resolver the list of versions including the yanked information. Semantics via `packaging`.
- **npm**: `https://registry.npmjs.org/{name}`. `dist-tags.latest` is the recommended latest;
  `versions` is a map of all versions; `repository` in the metadata. Semver semantics (different from
  Python).
- **Packagist**: `https://repo.packagist.org/p2/{vendor}/{package}.json` returns the package versions;
  metadata (repo, homepage) is available. Composer/semver semantics.
- Each provider maps to `PackageInfo` (`name`, `ecosystem`, `versions`, repo/homepage/changelog URL
  when present) and uses `resolve_latest` for `latest` (with an optional `constraint`/`allow_prerelease`).
- **Bonus trick (from the concept):** registry metadata almost always carry a URL to the
  documentation/repo. Return it in `PackageInfo` - the agent can then run that URL through the
  `scrape` tool and get current docs with no RAG.
- Use the shared httpx client. Handle a nonexistent package (404) and errors cleanly.

## Acceptance criteria

- [ ] For each ecosystem: a lookup of an existing package returns `PackageInfo` with `latest`, a list
      of versions, and a repo/homepage URL (where the registry provides it).
- [ ] A `constraint` propagates into the resolver and returns the correct satisfying version.
- [ ] Pre-release and (for PyPI) yanked versions are correctly excluded from `latest`.
- [ ] A nonexistent package is handled (a clear indication, not a traceback).
- [ ] Tests against **fixtures** (stored registry responses) for all three providers.
- [ ] ruff-clean, async, typed.

## How to verify

```bash
python -c "import asyncio; from solocrawl.core.packages.providers.pypi import PyPIProvider; \
print(asyncio.run(PyPIProvider().get_package('django')))"
pytest tests -k "pypi or npm or packagist"
```

## Notes / references

- PyPI JSON: `https://pypi.org/pypi/{name}/json` (watch the `yanked` flag at the level of release files).
- npm: `https://registry.npmjs.org/{name}` (`dist-tags.latest`).
- Packagist: `https://repo.packagist.org/p2/{vendor}/{package}.json`.
- Verify the current shape of the responses if you have tools - reality takes precedence.
