# Maintenance implementation — 2026-10

The approved audit plan is implemented in the current checkout. Version 1.1.0 and its
[release notes](release/1.1.0.md) are prepared; publication is a separate action.
User-driven checks confirmed offline, MCP, Chromium,
packaging, patched dependencies and live providers. The unsupported Reddit adapter was removed;
SearXNG remains optional and unverified without a configured instance.

| Area | Implemented behavior |
|------|----------------------|
| Configuration | Positive concurrency/size/finite timeout, non-negative retries/TTL, clear setting errors; built-in provider factories receive the supplied Config and legacy zero-argument factories remain compatible. |
| Proxy | Dead endpoints lose sticky assignments; exhaustion raises public `ProxyUnavailableError`; no direct fallback. HTTP and browser robots use the selected proxy; credentials are encoded/separated and redacted in error output. |
| HTTP policy | Every redirect checks URL/DNS and the target's robots before sending; cache entries cannot cross configuration policies. |
| Browser policy | Intercepts frames and subresources before requests, fetches at most one redirect hop, preserves main-page final URL, blocks service workers/WebSockets, propagates unsafe navigation errors. Redirected child-frame/resources abort to preserve credentials and origin isolation. |
| Versions | Complete grammar consumption; correct partial/hyphen/caret/tilde/wildcard bounds and SemVer prerelease ordering; PyPI keeps PEP 440. Maven/NuGet/RubyGems keep numeric four-part releases. Partial primitive comparators expand; partial `!=` and unsupported native ranges are rejected. |
| Registries | PyPI ignores empty/all-yanked releases but keeps mixed yanking; Swift follows validated tag pagination; Go escapes uppercase module paths in both endpoints. |
| Dependencies/MCP | FastMCP 4.0.10+ below 5, MCP SDK v2 field access, tested dependency floors including vulnerable transitive packages and dev pip. Five public tool names/signatures/text/stdio preserved; core HTTP remains httpx. |
| Docs/CI | Existing roadmap and release links repaired; documented policies and range subset. CI quality/packaging, separate local Chromium fixtures, and manually selected live checks use current Actions. |
| Verification | One Python runner, stable IDs, redacted JSON reports, meaningful pass/fail/blocked/skip statuses, clean wheel installations with all extras and independent live-provider checks. |

## Verification evidence and known limitations

A clean temporary Python 3.14 environment installed the current dependencies and FastMCP 4.
The user confirmed Ruff, formatting, Pyright, 443 offline fixture/MCP tests, MCP protocol,
real Chromium, wheel/sdist builds and independent base/browser/all clean installations.
The browser feedback exposed an aborted-navigation race: a verified main-page redirect now closes
the aborted page and opens the target in a fresh page within the same browser context.

The user's installed environment audit found 25 advisories in eight packages. Updating only direct
dependencies had retained older, already-satisfied transitive packages. Requirements now enforce
tested patched floors for AnyIO, cryptography, h2, hpack, Pydantic Settings, PyJWT and Soup Sieve;
the dev extra includes patched pip. Reinstallation with these floors passed dependency consistency
and the vulnerability audit in both the temporary environment and the user's updated `.venv`.
The user also repeated offline, MCP and Chromium checks successfully after upgrading dependencies.
Audit/outdated JSON is no longer truncated,
and audit descriptions are omitted to keep advisory IDs and fixed versions readable.

The user installed the security updates and removed the empty leftover
`~ncalled_for-0.3.2.dist-info` directory from an interrupted uninstall; the metadata warning is gone.
Missing distribution metadata now produces a warning rather than crashing report generation.
Sandbox policy prevented changing those installed files here; local validation used a temporary
environment. Git branch creation was also sandbox-blocked; the changes remain in the existing checkout.

The user's live run passed all ten package registries, eight search providers, federation, fetch,
research and batch (22 checks). arXiv passed a subsequent isolated check in 1.02 seconds, bringing
the verified live checks to 23. Its initial 30-second timeout did not reproduce; the exact cause was
not confirmed. Its log now identifies the exception type even when the exception message is empty.
SearXNG remains unverified because it was unconfigured. Reddit returned HTTP 403; current official
access guidance requires OAuth. The user chose to remove the anonymous adapter rather than add
account/token management. Its code, registration, unit/live tests and verification check were removed;
arXiv and SearXNG remain available. Older configurations enabling `reddit` no longer select it.

See [verification commands and feedback format](verification.md), then work through the
[release checklist](release/CHECKLIST.md). A blocked result remains pending, not a release pass.
