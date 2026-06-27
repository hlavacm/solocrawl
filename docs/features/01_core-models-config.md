# Feature 01: Core models & config

## Goal

Define the shared data types (normalized outputs) and the central configuration. These types are the
"contract" between layers - the core, the MCP shell, and the CLI all use them.

## Context

Normalized output types let fusion and the shells be independent of the concrete provider.
Configuration must have sensible defaults that work with no configuration at all (see `project.md`
goal 1).

## Dependencies

- Requires done: 00
- Blocks: practically everything

## Scope

Belongs here: `core/models.py` with the data types, `config.py` with loading configuration from env
+ defaults. Does not belong here: the logic that produces those types (later features do that).

## Implementation guidance

Data types (as `@dataclass`, shape is the agent's call):

- `SearchResult`: `title`, `url`, `snippet`, `source` (provider name), `score` (float, default 0).
  Optionally `raw` (original data) - optional.
- `FetchResult`: the result of a fetch - `url` (final after redirects), `content` (markdown),
  `content_type`, `status`, a flag for whether the browser was used. Whatever makes sense.
- `PackageInfo`: `name`, `ecosystem`, `latest` (resolved version), `versions` (a few recent ones),
  `repository`/`homepage` URL, optionally a `changelog` URL when available.

Configuration (`config.py`):

- Loads from env with the `SOLOCRAWL_` prefix. Key items:
  - concurrency: global max concurrent fetches, per-domain limit, timeouts, retries
  - proxy: enabled (default false), mode (list/endpoint), proxy source, auth
  - opt-in providers: which to enable (e.g. `SOLOCRAWL_ENABLE_PROVIDERS=arxiv,hackernews`)
  - browser: whether Playwright is available / allowed
- **All defaults must yield working behavior with no settings.** Configuration only tunes/enables extras.
- Consider a simple config object (dataclass / pydantic settings) loaded once.

## Acceptance criteria

- [ ] `core/models.py` defines `SearchResult`, `FetchResult`, `PackageInfo` (fully typed).
- [ ] `config.py` loads configuration from env and provides sensible defaults with no env variable.
- [ ] Configuration is available as one easily importable object/function.
- [ ] Tests: defaults work without env; env variables correctly override defaults; parsing the list
      of opt-in providers works.
- [ ] ruff-clean, typed.

## How to verify

```bash
python -c "from solocrawl.config import load_config; print(load_config())"
pytest tests -k config
```

## Notes

Do not over-engineer the config - just what later features actually use. You can extend it as you go,
but try to stabilize the shape of the types in `models.py` early, so they can be relied upon.
