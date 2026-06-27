# Feature NN: <name>

> Template for a single feature. Copy it for new features. Keep the tone: enough context and
> guidance, but not prescriptive step-by-step code. Leave the agent room for judgment within the
> principles.

## Goal

In one or two sentences: what this feature adds and why. (Value, not implementation.)

## Context

Where it fits in the architecture, what it builds on (which previous features must be done), and
what will build on this. Reference the relevant part of `context/architecture.md`.

## Dependencies

- Requires done: feature NN, NN
- Blocks (waiting on this): feature NN

## Scope

What **belongs** in this feature and what **does not** (moves elsewhere / is out of scope). This is
important so the feature does not sprawl.

## Implementation guidance

Direction, not dictation. Key modules, the shape of interfaces (illustrative), what to watch out for,
what the traps are. The agent may refine the shape, as long as it preserves the intent and the
principles in `context/`.

## Acceptance criteria

Concrete, verifiable items. This is the contract - the feature is done when these hold.

- [ ] ...
- [ ] ...

## How to verify (manual test)

A concrete command or procedure by which the human (and the agent) confirms it works. Ideally a CLI
command or a short snippet of code.

## Notes / references

Useful links (endpoints, documentation), notes on the current state of the external world.
