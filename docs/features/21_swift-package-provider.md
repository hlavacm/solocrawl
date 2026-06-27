# Feature 21: Swift package provider

## Goal

Add Swift to the package-version lookup, using the same provider/registry pattern as the other
ecosystems.

## Context

Builds on the package provider interface and resolver (feature 10) and the shared fetch client.
Unlike PyPI/npm/etc., Swift has no classic version registry — releases are git tags (semver) on the
package repository. The Swift Package Index itself indexes versions from those tags. So this provider
resolves versions from the **GitHub tags API** for an `owner/repo` identifier.

## Dependencies

- Requires done: 10, 02
- Blocks: -

## Scope

Belongs here: a `swift` provider resolving tags from `api.github.com/repos/{owner}/{repo}/tags`, with
`owner/repo` (or a github.com URL) as the name, plus CLI/MCP wiring. Does not belong: non-GitHub hosts,
the Swift Package Registry (SE-0292) protocol, or authenticated GitHub access.

## Implementation guidance

- `core/packages/providers/swift.py`: `@register("swift", ecosystem="swift", zero_config=True)`. Parse
  the identifier (accept `owner/repo`, a `github.com/...` URL, optional `.git`). Fetch tags
  (`?per_page=100`, header `Accept: application/vnd.github+json`), keep version-like tags, and resolve
  via `build_package_info(..., constraint_parser=parse_semver_constraint)`. Repository is the GitHub
  URL. 404 → `PackageNotFoundError`. Works unauthenticated (rate-limited).
- Register the import in `providers/__init__.py`; add `swift` to `SUPPORTED_ECOSYSTEMS` and the
  CLI/MCP help.

## Acceptance criteria

- [ ] `solocrawl package apple/swift-argument-parser --ecosystem swift` returns the latest stable tag.
- [ ] `--constraint` selects the highest satisfying tag; pre-releases excluded unless
      `--allow-prerelease`.
- [ ] Non-`owner/repo` names and missing repos produce a clear error.
- [ ] Fixture tests cover parsing, constraint, prerelease, and the 404 path.

## How to verify (manual test)

```bash
solocrawl package apple/swift-argument-parser --ecosystem swift
solocrawl package pointfreeco/swift-composable-architecture --ecosystem swift --constraint ">=1,<2"
```

## Notes / references

GitHub REST "List repository tags": `GET /repos/{owner}/{repo}/tags`, array of `{name, commit, …}`.
Only the first 100 tags are considered (enough for latest + recent).
