# Prompt: Implement a feature

> Send this to the agent when you want it to do a specific feature. Fill in the feature number.

---

You are working on the **SoloCrawl** project. Before you write anything, load and take into account this
context:

- `docs/context/project.md` (what we are building, scope, **non-goals**)
- `docs/context/architecture.md` (how it should be assembled and why)
- `docs/context/conventions.md` (how to write the code)
- `docs/context/agent-workflow.md` (how to proceed and when it is done)

Then implement **feature number: `<FILL IN NUMBER>`**, whose brief is in `docs/features/<NN>_*.md`.
Read it in full, including dependencies and acceptance criteria, and glance at
`docs/features/ROADMAP.md` so you know what you are building on.

Rules:
- Stick to the **scope of that one feature**. Do not do several at once or a big refactor around it.
- Treat the brief as direction, not dictation - you have room for your own reasonable judgment, but
  **never cross the scope and non-goals** in `project.md`. Mention significant decisions in the summary.
- If reality (an API shape, a package name, an endpoint) differs from the description and you have
  tools to verify, **verify the current state** - reality takes precedence over the text in the docs.
- Follow the **Definition of Done** from `agent-workflow.md`. In particular, before you call the
  feature done, the **mandatory quality gate must pass**: `ruff check` + `ruff format --check`,
  `pyright` (no type errors), and `pytest` (green). Run this gate at the end of the task and fix until
  all three are green. Acceptance criteria met, code per the conventions, tests against fixtures,
  nothing existing broken, the project runnable.

At the end, give a short summary: **Done** / **Files** / **Decisions** (deviations) / **How to verify**
(a concrete command) / **Next** (which feature follows).
