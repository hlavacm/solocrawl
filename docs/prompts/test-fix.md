# Prompt: Run the tests and fix

> Send to the agent after implementing a feature (or anytime) to confirm everything is green and clean.

---

You are working on the **SoloCrawl** project. The goal now is not new functionality, but to **bring the
project to a green, clean state**. If needed, refresh the context from `docs/context/conventions.md`
and `docs/context/agent-workflow.md`.

Do the following:

1. Run lint and formatting: `ruff check .` and `ruff format --check .`. Fix the findings (formatting
   automatically is fine; logical findings judiciously).
2. Run static type analysis: `pyright`. Fix all type errors (this is the CLI engine behind Pylance,
   so it matches what you see in the editor). Do not silence errors with blanket `# type: ignore` -
   fix the actual type problem; use a narrow, commented ignore only when a third-party stub is genuinely
   missing or wrong.
3. Run the tests: `pytest`. For each failure, find the cause and fix it - **either in the code or in
   the test**, depending on what is actually wrong (do not adjust a test to hide a real bug).
4. Check that the provider tests run **against fixtures**, not against the live web. If something calls
   live endpoints in normal CI, move it behind a marker / replace it with a fixture.
5. Verify there is no **blocking I/O** on the async path and that the principles from the conventions
   were not broken (shared httpx client, bounded concurrency, graceful degradation).
6. If relevant, manually verify the main path (e.g. `solocrawl search ...`, `solocrawl package ...`).

The goal is the full **quality gate green**: `ruff` ✓, `pyright` ✓, `pytest` ✓.

Rules:
- Keep the fixes **minimal and targeted**. No refactor "while you're at it".
- When you hit a deeper problem outside the scope (a flawed design, something large), **leave it be
  and report it** in the summary instead of quietly rewriting it.

At the end, give a summary: what was wrong, what you fixed, what the state is now (`ruff` ✓,
`pyright` ✓, `pytest` ✓), and optionally what remains as an open problem to decide.
