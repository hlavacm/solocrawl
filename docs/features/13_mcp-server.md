# Feature 13: MCP server (FastMCP, stdio)

## Goal

Expose the core as an MCP server over stdio, so LM Studio, OpenCode, Claude Desktop, and others can
use it. This is the project's main goal - after this feature SoloCrawl is usable where it was built for.

## Context

The MCP shell is **thin** - it only calls the core and serializes the output, no logic (see
`architecture.md` `mcp/`). LM Studio supports MCP from 0.3.17, via `mcp.json` in Cursor notation;
local stdio servers work normally (FastMCP). Tools need good docstrings - **the model sees them**.

## Dependencies

- Requires done: 06 (federation), 09 or at least federation+providers, 11 (packages)
- Blocks: -

## Scope

Belongs here: the MCP server on FastMCP/stdio, the tools `web_search`, `scrape`, `package_version`,
their docstrings and output serialization, an example configuration for LM Studio. Does not belong
here: new core logic.

## Implementation guidance

- Build on FastMCP (the Python MCP SDK). Entry point `python -m solocrawl.mcp`. Transport **stdio**
  (`mcp.run()` defaults to stdio).
- Tools (names/parameters can be refined, but keep them clear for the model):
  - `web_search(query: str, limit: int = 5, sources: list[str] | None = None) -> ...`
    - calls `federated_search` with the selected/active providers; returns a structured list of results
  - `scrape(url: str) -> ...` - calls fetch+extract, returns markdown
  - `package_version(name: str, ecosystem: str, constraint: str | None = None,
    allow_prerelease: bool = False) -> ...` - calls the package layer
- **Tool docstrings** must clearly describe the purpose and parameters - the model decides when to
  call a tool based on them. Concise but expressive.
- Serialize the output into a form the model handles well (readable markdown or structured JSON-like
  content; for search consider a compact title+url+snippet format so it does not eat context).
- Lifecycle: correctly open/close the shared httpx client (and later the browser) within the server's run.
- Add to the repo an **example `mcp.json`** for LM Studio (stdio, command = the python venv, args =
  `-m solocrawl.mcp`) and a short guide in the README/release.

## Acceptance criteria

- [ ] `python -m solocrawl.mcp` starts the stdio MCP server without error.
- [ ] The server exposes the tools `web_search`, `scrape`, `package_version` with descriptive docstrings.
- [ ] The tools really call the core and return meaningful, model-readable output.
- [ ] The repo has a working example `mcp.json` for LM Studio + a short guide on wiring it up.
- [ ] At least a basic test/verification that the tools register and are callable (the core can be mocked).
- [ ] ruff-clean.

## How to verify

- Locally: run `python -m solocrawl.mcp`, optionally test with the MCP inspector or directly in LM
  Studio via `mcp.json`.
- Verify that the model in LM Studio sees the tools and can call `web_search` / `scrape` /
  `package_version`.

## Notes / references

- LM Studio MCP: `mcp.json` in Cursor notation (`mcpServers`), local stdio servers supported from
  0.3.17. Verify the current wiring details if you have tools - build the shell on a transport the
  target LM Studio version supports (stdio is a safe choice).
- Keep the shell thin: any extra logic belongs in the core, not here.
