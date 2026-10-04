# Project verification

Use Python 3.14 or newer in a virtual environment. Update the checkout's environment before testing:

```bash
python -m pip install --upgrade "pip>=26.2.1"
python -m pip install --upgrade -e ".[dev,browser]"
python -m playwright install chromium
```

The browser extra is optional for the ordinary quality gate. The current MCP dependency is
`fastmcp>=4.0.10,<5`; SoloCrawl's HTTP providers continue to use `httpx`.

## Run checks and share feedback

From the repository root, use the same Python interpreter that installed the package:

```bash
python scripts/verify_project.py --mode offline
python scripts/verify_project.py --mode mcp
python scripts/verify_project.py --mode browser
python scripts/verify_project.py --mode dependencies
python scripts/verify_project.py --mode packaging
python scripts/verify_project.py --mode live
```

`--mode all` runs every group. `--list` displays stable check IDs. To rerun an individual failure:

```bash
python scripts/verify_project.py --check search-wikipedia
python scripts/verify_project.py --check package-go
python scripts/verify_project.py --check audit
```

Each run prints a short outcome and writes a JSON report under `artifacts/verification/`. Use
`--json path/to/report.json` to choose a destination and `--timeout 600` for slower clean installs.
Share that JSON or the check ID and terminal diagnostics as feedback. Reports include Python,
platform, installed versions and check output; they exclude environment contents and redact URL
credentials and configured secret values. Review diagnostics before sharing them publicly.
Audit and outdated JSON output is retained in full. Audit includes advisory IDs and fixed versions;
long advisory descriptions are omitted. Missing installed distribution metadata is reported in
`metadata_warnings` without preventing report creation.

Runtime requirements include tested security floors for AnyIO, cryptography, HTTP/2, HPACK,
Pydantic Settings, PyJWT and Soup Sieve. These also update vulnerable transitive packages in an
existing environment when reinstalling SoloCrawl; pip's default upgrade strategy otherwise often
keeps already-satisfied transitive versions. The dev extra also requires the patched pip version.

| Status | Meaning |
|--------|---------|
| `pass` | Check ran and met its assertions. The outdated inventory is informational. |
| `fail` | Check ran and found a defect, inconsistency or reported vulnerability. |
| `blocked` | A required tool, browser binary, network endpoint or prerequisite was unavailable. |
| `skip` | An optional provider needs configuration, such as `SOLOCRAWL_SEARXNG_URL`. |

Exit codes are `0` for completed checks (including optional skips), `1` if any check failed and `2`
if checks were blocked without a detected failure. A missing browser is never counted as a pass.
Explicitly requesting an unconfigured optional provider with `--check` returns `blocked`.

## What each group covers

- **offline**: Ruff lint and formatting, Pyright with the selected interpreter, all fixture tests
  including MCP protocol tests, and `pip check`. Ordinary fixture tests cannot launch a real browser.
- **mcp**: real FastMCP clients check exactly five tool names and schemas, text results, readable
  configuration errors, the subprocess stdio entry point and shutdown. The camelCase compatibility
  bridge is disabled so SDK v2 snake_case attributes are exercised.
- **browser**: actual Chromium against local Python fixtures. Checks JavaScript rendering,
  redirects, `robots.txt`, blocked iframe/script/fetch requests, service workers, WebSockets and the explicit
  internal-URL override. The fixture admits one local origin while other targets use real safety
  checks; it does not need internet access, a proxy account or API keys.
- **dependencies**: installed dependency consistency, outdated inventory and `pip-audit`. Audit
  queries require network access. This group never changes installed packages or applies fixes.
- **packaging**: wheel and sdist build, then separate temporary environments install the wheel's
  base, browser and all extras. Checks installed CLI entry points and MCP import. Dependency
  downloads need network access; Chromium is not installed automatically by this group.
- **live**: each search provider and each package registry separately, then federation, scraping,
  research and batch. Empty provider results fail even if another source could cover for them.
  SearXNG is skipped unless its URL is configured. Live endpoint failures can be environmental;
  return their diagnostics so we can distinguish endpoint changes from access restrictions.

Browser main-page redirects retain their final URL. Redirected iframe, script and XHR subrequests
are aborted after validating the destination: replaying them through Playwright's fetch API would
change browser origin/relative-URL semantics and could forward authorization or POST bodies. This
restriction may prevent some pages from rendering completely. Ordinary HTTP redirects still work.

Native commands remain supported:

```bash
ruff check .
ruff format --check .
pyright
pytest
pytest -m mcp
pytest -m browser
pytest -m live
```

The default pytest selection excludes `live` and `browser`. Install the browser extra and Chromium
before selecting `browser`; tests deliberately fail if rendering is unavailable.
