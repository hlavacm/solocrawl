# Repository Guidelines

## Project Structure & Module Organization

SoloCrawl is a Python 3.14+ package using a `src/` layout. Core library code lives in
`src/solocrawl/core/`, with subpackages for `fetch`, `extract`, `search`, `packages`, and `proxy`.
CLI adapters are in `src/solocrawl/cli/`; MCP stdio code is in `src/solocrawl/mcp/`. Tests live
in `tests/`, examples in `examples/`, assets in `assets/`, and design notes in `docs/context/`.

Keep business logic in `core`; CLI and MCP code should remain thin serialization and command shells.

## Build, Test, and Development Commands

- `python -m venv .venv && source .venv/bin/activate`: create a local virtualenv.
- `pip install -e ".[dev]"`: install the package plus dev tools.
- `solocrawl search "python asyncio" --limit 5`: run the CLI after editable install.
- `solocrawl-mcp`: start the MCP server on stdio.
- `ruff check .` and `ruff format --check .`: lint and verify formatting.
- `pyright`: run static type checking.
- `pytest`: run the default test suite, excluding tests marked `live`.
- `pytest -m live`: run optional network smoke tests.

## Coding Style & Naming Conventions

Use Ruff formatting with a 100-character line length and Python 3.14 target. Prefer full type hints,
especially on public interfaces. Use `snake_case` for functions and variables, `PascalCase` for
classes, and `UPPER_SNAKE` for constants. Public functions/classes need short behavior-focused
docstrings; MCP tool docstrings must be clear because clients surface them to models.

Async code is the default for network paths. Avoid blocking calls such as `requests` or `time.sleep`.

## Testing Guidelines

Tests use `pytest` with `pytest-asyncio`; test files follow `tests/test_*.py`. Normal tests should use
fixtures or mocked responses instead of the live web. Mark network smoke tests with
`@pytest.mark.live` so they stay out of the default run.

Add tests for provider parsing, graceful degradation, resolver edges, extraction fallbacks, and CLI or
MCP behavior when changing those areas.

## Commit & Pull Request Guidelines

Recent commits use short imperative summaries such as `Fix version, mcp startup info & close process`
and `Increase tests code coverage`. Keep commits small and thematic.

Pull requests should include a concise description, linked issue or feature note when applicable, gate
results for `ruff`, `pyright`, and `pytest`, and terminal output when CLI behavior changes.

## Security & Configuration Tips

Configuration is environment-based and prefixed with `SOLOCRAWL_`. Defaults should work with no
secrets or accounts. Never commit API keys, proxy credentials, or local logs. Preserve URL safety
checks for literal hosts, DNS-resolved internal addresses, redirects, browser final URLs, and
cloud-metadata targets.
