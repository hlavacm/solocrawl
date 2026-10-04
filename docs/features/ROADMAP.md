# Feature roadmap

Numbered feature briefs describe the existing implementation, not a promise of future APIs.
Read a brief together with the actual code and current regression tests.

| Feature | State |
|---------|-------|
| [Feature 00: Project skeleton](00_project-skeleton.md) | Implemented; verify with current gates |
| [Feature 01: Core models & config](01_core-models-config.md) | Implemented; verify with current gates |
| [Feature 02: Fetch (httpx) & extract](02_fetch-extract.md) | Implemented; verify with current gates |
| [Feature 03: CLI skeleton](03_cli-skeleton.md) | Implemented; verify with current gates |
| [Feature 04: Search provider interface + registry](04_search-provider-interface.md) | Implemented; verify with current gates |
| [Feature 05: Wikipedia provider](05_wikipedia-provider.md) | Implemented; verify with current gates |
| [Feature 06: Federation + RRF fusion](06_federation-fusion.md) | Implemented; verify with current gates |
| [Feature 07: DuckDuckGo provider (`ddgs`)](07_duckduckgo-provider.md) | Implemented; verify with current gates |
| [Feature 08: StackExchange provider](08_stackexchange-provider.md) | Implemented; verify with current gates |
| [Feature 09: CLI `search`](09_cli-search.md) | Implemented; verify with current gates |
| [Feature 10: Package provider interface + resolver](10_package-interface-resolver.md) | Implemented; verify with current gates |
| [Feature 11: PyPI / npm / Packagist providers](11_package-providers.md) | Implemented; verify with current gates |
| [Feature 12: CLI `package`](12_cli-package.md) | Implemented; verify with current gates |
| [Feature 13: MCP server (FastMCP, stdio)](13_mcp-server.md) | Implemented; verify with current gates |
| [Feature 14: Playwright fallback](14_playwright-fallback.md) | Implemented; verify with current gates |
| [Feature 15: Proxy layer (Webshare model)](15_proxy-layer.md) | Implemented; verify with current gates |
| [Feature 16: Opt-in search providers](16_optin-providers.md) | Implemented; verify with current gates |
| [Feature 17: Release & packaging](17_release-packaging.md) | Implemented; verify with current gates |
| [Feature 18: Provider discoverability](18_provider-discoverability.md) | Implemented; verify with current gates |
| [Feature 19: robots.txt enforcement](19_robots-txt-enforcement.md) | Implemented; verify with current gates |
| [Feature 20: Extraction metadata](20_extraction-metadata.md) | Implemented; verify with current gates |
| [Feature 21: Swift package provider](21_swift-package-provider.md) | Implemented; verify with current gates |
| [Feature 22: Opt-in search providers (GitHub, MDN, SearXNG)](22_optin-search-providers.md) | Implemented; verify with current gates |
| [Feature 23: Lightweight fetch TTL cache](23_fetch-cache.md) | Implemented; verify with current gates |
| [Feature 24: Research tool (search → scrape → aggregate)](24_research-tool.md) | Implemented; verify with current gates |
| [Feature 25: Batch scrape + live smoke tests](25_batch-and-live-smoke.md) | Implemented; verify with current gates |

The 2026 maintenance pass covers configuration, proxy failure policy, safe redirects and browser
requests, version resolution, FastMCP 4, packaging, CI and verification reports. See
[verification](../verification.md) and the [release checklist](../release/CHECKLIST.md).
Checks requiring unavailable services remain pending until their reports are reviewed.
