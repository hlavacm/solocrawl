<p align="center">
  <img src="../assets/icon/solocrawl.png" alt="SoloCrawl logo" width="96">
</p>

# SoloCrawl - development documentation

SoloCrawl is a self-hosted, fully asynchronous **web search + scraping + package-version** tool
written in Python, exposed as an **MCP server** for local LLM tooling (LM Studio, OpenCode, Claude
Desktop, and others). Secondarily it works as a library and as a CLI.

This `docs/` folder is written so that an AI agent (Claude Code, Codex, etc.) can build the project
step by step, with enough context but without being overly prescriptive.

## How this is organized

```
docs/
├── README.md              <- you are here: map and way of working
├── context/               <- STABLE context, read before every task
│   ├── project.md             vision, goals, scope, non-goals
│   ├── architecture.md        how the system is assembled and why
│   ├── conventions.md         coding conventions, style, dependencies
│   └── agent-workflow.md      how the agent should work (process, definition of done)
├── features/              <- INCREMENTALLY assigned units of work
│   ├── _template.md           template for a single feature
│   ├── 00_project-skeleton.md
│   ├── 01_...                 (numbered in recommended build order)
│   └── ROADMAP.md             overview and dependencies between features
├── prompts/               <- REUSABLE prompts
│   ├── implement-feature.md   "build feature N"
│   ├── test-fix.md            "run the tests and fix"
│   └── code-review.md         "review the latest work"
└── release/
    ├── README.md              how it is packaged and released
    └── CHECKLIST.md           pre-release checklist
```

## Recommended way of working (for the human)

1. At the start, have the agent read the whole of `docs/context/` (four files). That is its mental model.
2. Whenever you want to implement the next feature, send it the contents of `prompts/implement-feature.md`
   and give the feature number (e.g. "feature 03"). The agent loads `features/03_*.md` and proceeds.
3. After implementation, use `prompts/test-fix.md` to get tests green and `prompts/code-review.md`
   for quality.
4. Take features in numeric order / per `features/ROADMAP.md` - they are sequenced so each one builds
   on what is done, and the project is runnable after each one.

## Recommended way of working (for the agent)

Before writing anything: read `context/project.md`, `context/architecture.md`,
`context/conventions.md`, and `context/agent-workflow.md`. Only then open the assigned feature in
`features/` and proceed per `agent-workflow.md`. When something is missing or contradictory in the
brief, follow the principles in `context/` and decide sensibly - the room for judgment is
intentional, but stay within the scope and non-goals in `project.md`.

## Current verification and releases

[Verification runner and feedback](verification.md) · [Feature roadmap](features/ROADMAP.md) ·
[Release instructions](release/README.md) · [Release checklist](release/CHECKLIST.md)

[Maintenance implementation and verification limits](maintenance.md)
