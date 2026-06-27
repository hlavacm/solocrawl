# Feature 00: Project skeleton

## Goal

Prepare the repository skeleton: directory structure, `pyproject.toml`, lint/formatter, empty (but
importable) modules, and basic CI. After this feature the project can be installed and tested, even
though it does nothing yet.

## Context

This is the zeroth step everything else builds on. The goal is the correct layout per
`context/architecture.md`, not functionality. Keep the core/mcp/cli layout separated.

## Dependencies

- Requires done: nothing
- Blocks: everything else

## Scope

Belongs here: package structure, build configuration, lint, empty modules with `__init__.py`, a
placeholder for tests, a CI workflow, `.gitignore`, a skeleton of the repo's main `README.md` (short;
the full README is feature 17). Does not belong here: any real fetch/search/packages logic.

## Implementation guidance

- A `src/solocrawl/` package with submodules per `architecture.md` (`core/`, `core/fetch/`,
  `core/extract/`, `core/search/`, `core/search/providers/`, `core/packages/`,
  `core/packages/providers/`, `core/proxy/`, `mcp/`, `cli/`). Each module should be importable (an
  empty `__init__.py` is enough).
- `pyproject.toml`: project metadata, dependencies (for now only the certain ones - `httpx`; the rest
  are added in their respective features), dev dependencies (`pytest`, `pytest-asyncio`/`anyio`,
  `ruff`, `pyright`). Consider splitting into extras (e.g. `[browser]` for playwright, `[all]`) so the
  default install is light.
- Set up **ruff** (lint + format) with a reasonable configuration. Goal: `ruff check` passes.
- Set up **Pyright** for static type analysis (the CLI engine behind Pylance). Configure it in
  `pyproject.toml` (`[tool.pyright]`) or `pyrightconfig.json`, mode **standard** (see conventions).
  Goal: `pyright` passes on the (empty) skeleton.
- Simple CI (GitHub Actions): on push, run ruff, pyright, and pytest. Keep it minimalist. This CI
  encodes the mandatory quality gate from `conventions.md` / `agent-workflow.md`.
- A short `README.md` in the root: a one-paragraph description + "under construction, see docs/".
  The full version is handled by feature 17.
- Consider whether the project will be installable (`pip install -e .`) - yes, so the console entry
  points work later (`solocrawl` CLI, `python -m solocrawl.mcp`).

## Acceptance criteria

- [ ] `pip install -e .` (with dev extras) runs without error.
- [ ] The directory structure matches `architecture.md`; all modules are importable.
- [ ] `ruff check` and `ruff format --check` pass.
- [ ] `pyright` passes (configured in standard mode).
- [ ] `pytest` runs (even 0 or 1 trivial test) and is green.
- [ ] A CI workflow exists and runs the full gate: lint + type-check (pyright) + test.
- [ ] The root has a `.gitignore` (Python, venv, `__pycache__`, playwright cache, etc.).

## How to verify

```bash
pip install -e ".[dev]"
ruff check .
pyright
pytest
```

## Notes

Python version 3.14+ (see conventions). The entry points (CLI, MCP) are filled in for real later,
but feel free to already declare them in `pyproject.toml` so they don't have to change.
