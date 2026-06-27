# Prompt: Review the latest work

> Send to the agent (ideally in a fresh session, or to a different agent) for an independent review of
> a feature.

---

You are doing a **code review** of the latest work on the **SoloCrawl** project. First load the
yardsticks: `docs/context/architecture.md`, `docs/context/conventions.md`, `docs/context/project.md`
(especially the **non-goals**), and the brief of the reviewed feature in `docs/features/<NN>_*.md`.

Review - go through and assess:

1. **Acceptance criteria**: does the code meet all the criteria from the given feature? Specifically,
   point by point.
2. **Architecture**: does it respect the layers (core contains no MCP/CLI dependencies; the shells
   contain no logic)? Is the provider/registry pattern followed? Is the httpx-first / browser-fallback
   principle preserved?
3. **Conventions & quality gate**: typing, async (no blocking I/O), ruff-clean, **pyright with no type
   errors**, shared httpx client, bounded concurrency, graceful degradation, minimal dependencies.
   Confirm the mandatory gate (`ruff` ✓, `pyright` ✓, `pytest` ✓) actually passes.
4. **Scope and non-goals**: did anything forbidden creep into the code (an own DB of versions, RAG,
   bypassing ToS, a default provider with a key, needless over-engineering)?
5. **Tests**: do they cover the key behavior? Do they run against fixtures, not live? Are the edge
   cases (versions, fusion, fallback, a failing provider) handled?
6. **Robustness**: timeouts, retry/backoff on rate-limit, clean handling of errors and empty states.

Output of the review:
- **Verdict**: OK / minor reservations / send back for rework.
- **Findings** by severity (blocking / recommended / cosmetic), each with a concrete location and a
  suggested fix.
- **What is good** (briefly - so the feedback is balanced).

Be concrete and to the point. Do not rewrite the code yourself (unless the human asks) - this is a
review, the output is an assessment and recommendations.
