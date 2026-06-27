# Working process for the AI agent

This document states **how you, as the agent, should proceed** when working on SoloCrawl. It applies
to every feature you are assigned.

## Before you write the first line

1. Read `context/project.md` - what we are building, the scope, and above all the **non-goals**.
2. Read `context/architecture.md` - how it should be assembled and why.
3. Read `context/conventions.md` - how to write the code.
4. Open the assigned feature in `features/NN_*.md` and read it in full, including dependencies.
5. Glance at `features/ROADMAP.md` so you know what is done and what you are building on.

If something in the brief is missing or contradictory: **decide for yourself, sensibly**, based on
the principles in `context/`. The room for judgment is intentional. But never cross the scope and
non-goals in `project.md`. When a decision is significant (changes an interface, adds a dependency),
**note it briefly in your output** so the human sees it.

## How big a chunk to do

- Do **exactly one feature** from `features/`, not several at once, until told otherwise.
- Within a feature, proceed in small, verifiable steps.
- After finishing a feature, the project must be in a **runnable state** (see Definition of Done).

## Definition of Done (when a feature is finished)

Before you mark a feature as done, the **mandatory quality gate must pass**. This is a hard gate, run
at the end of the task (not after every single edit), and a feature is not done until all three are
green:

1. **`ruff check .`** and **`ruff format --check .`** - clean (lint + format).
2. **`pyright`** - no errors (static type analysis; this is the CLI engine behind Pylance).
3. **`pytest`** - green (tests against fixtures, not the live web).

In addition, a feature is done when:

- [ ] It meets the **Acceptance criteria** listed in its `features/NN_*.md`.
- [ ] The code complies with `conventions.md` (typing, async, no blocking I/O).
- [ ] The quality gate above passes (`ruff` ✓, `pyright` ✓, `pytest` ✓).
- [ ] It has **tests** for key behavior (against fixtures, not the live web) - tests are mandatory,
      not optional.
- [ ] It does not break existing features or tests from previous features.
- [ ] The project can be run after the feature (at least via the CLI, once the CLI exists).
- [ ] Public interfaces have short docstrings; MCP tools have a docstring describing purpose/parameters.
- [ ] You briefly summarize **what you did** and **what decisions you made** (especially deviations
      from the brief).

## Process within a feature (recommended rhythm)

1. **Think** - briefly outline how you will do it (which modules, which interfaces). No long essay.
2. **Implement** the core of the feature per the architecture.
3. **Write tests** for the key behavior.
4. **Run the quality gate** (`ruff check` + `ruff format --check`, `pyright`, `pytest`) and fix until
   all three are green.
5. **Verify manually** (e.g. a CLI command) that it actually works.
6. **Summarize** the result and decisions.

## When you hit external reality

Some things (API shapes, package names, endpoints) may differ from the description - the world
changes. When you hit that:

- Stick to the **intent** of the feature, not its literal wording.
- If you have tools available (web, code execution), **verify the current shape** (e.g. the PyPI JSON
  API response, `ddgs` parameters, the StackExchange filter). Verified real behavior takes precedence
  over what is written in the docs.
- Mention the change versus the brief in your summary.

## Boundaries and safety

- Do not implement the non-goals (RAG, own DB of versions, bypassing ToS/robots, paid default
  providers).
- Do not add a dependency without justification; when you must, justify it.
- Do not do a "big refactor around it" - stay within the feature's scope. When you see a need for a
  larger change, propose it to the human instead of just doing it.

## Format of your output to the human

At the end of work on a feature, give a short summary along these lines:

- **Done:** what now works (1-3 sentences).
- **Files:** which ones you created/changed.
- **Decisions:** significant choices and deviations from the brief (only if there were any).
- **How to verify:** a concrete command the human can use to confirm it works.
- **Next:** which feature logically follows.
