# Pre-release checklist

Record results for the exact checkout being released. A blocked check remains pending.

- [ ] Ruff lint and formatting pass.
- [ ] Pyright passes using the release environment's interpreter.
- [ ] Offline fixture tests and MCP client/stdio tests pass.
- [ ] Installed dependencies satisfy declared requirements (`pip check`).
- [ ] `pip-audit` reports no unresolved vulnerabilities; outdated inventory is reviewed.
- [ ] Local Chromium integration passes with current Playwright and browser binaries.
- [ ] Search providers and package registries pass individual live checks; explain optional skips.
- [ ] Live federation, fetch, research and batch pass.
- [ ] Wheel and sdist build successfully; wheel installs with base, browser and all extras.
- [ ] Installed CLI commands and MCP entry point work outside the checkout.
- [ ] README, examples and local documentation links match implemented behavior.
- [ ] Version and release notes are prepared; credentials and local reports stay out of Git.
- [ ] Separately authorize and perform tagging/publishing when a release is wanted.

See [verification commands and report format](../verification.md).
