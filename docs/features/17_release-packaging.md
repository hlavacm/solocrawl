# Feature 17: Release & packaging

## Goal

Bring the project to a "a stranger clones it and gets it running" state: a full README, examples, a
clean install, preparation for release. This is final polishing, not new functionality.

## Context

The project is open-source / reference (see `project.md`). Definition of success: a stranger has
working search and package lookup within a few minutes, with no account/key, and the code is clean
enough to add a provider.

## Dependencies

- Requires done: everything above (00-16, at least the core 00-13)
- Blocks: -

## Scope

Belongs here: the root README, install/usage documentation, examples (CLI and MCP), a check of the
extras, preparation for publication. Does not belong here: new core functionality.

## Implementation guidance

- **README** in the root: what it is, why, a quick start (install, the first
  `scrape`/`search`/`package`), wiring into LM Studio (an example `mcp.json`), an overview of the
  providers (default vs. opt-in), how to add your own provider (a short guide - this architecture
  should make it easy), a section on respecting robots.txt/ToS, a license.
- **Install extras**: verify that the default install is light and `[browser]`/`[all]` work;
  `playwright install` mentioned only where needed.
- **Examples**: short demos of the CLI and of programmatic use of the core as a library; an example
  `mcp.json`.
- **Release**: see `docs/release/CHECKLIST.md` and `docs/release/README.md` - go through them.
  Versioning (SemVer), a changelog, optionally publishing to PyPI (optional), a tag.
- Go through and confirm the defaults work with no configuration and that "clean clone → run"
  actually passes.

## Acceptance criteria

- [ ] The root README covers: purpose, quick start, LM Studio wiring, provider overview, how to add a
      provider, the robots/ToS note, the license.
- [ ] A clean install from scratch works; the extras (`browser`/`all`) work.
- [ ] The examples (CLI, library, `mcp.json`) are functional and tested.
- [ ] `docs/release/CHECKLIST.md` passes in full.
- [ ] The project is in a state fit for release (tag/version, changelog).

## How to verify

```bash
# simulating a "stranger user" in a clean environment
git clone <repo> && cd solocrawl
pip install -e .
solocrawl search "python asyncio" --limit 3
solocrawl package requests --ecosystem pypi
```

## Notes

The goal is the first impression: the quick start must actually work on a clean machine with no keys.
If something requires an extra step, either remove it from the quick start (into "advanced") or
automate it.
