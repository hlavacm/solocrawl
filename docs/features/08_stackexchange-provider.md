# Feature 08: StackExchange provider

## Goal

Add programming Q&A into the default set via the official StackExchange API (Stack Overflow and
sibling sites). For the project's dev audience, one of the most valuable sources.

## Context

The official API `api.stackexchange.com/2.3` works without a key (only a lower daily quota per IP).
A specific: the body of questions/answers must be explicitly requested via a filter - see guidance.
See `architecture.md` `core/search/`.

## Dependencies

- Requires done: 04
- Blocks: 09, 13

## Scope

Belongs here: a StackExchange provider (zero-config), two-phase content retrieval, mapping to
`SearchResult`, handling of rate-limits. Does not belong here: other providers.

## Implementation guidance

- The `search/advanced` endpoint on `api.stackexchange.com/2.3`, parameter `site` (default
  `stackoverflow`), sort by relevance, `pagesize` per `limit`.
- **Two-phase content**: by default answers are truncated - the body is returned only with a suitable
  `filter` (e.g. an equivalent of `withbody`). If you want a useful snippet in `SearchResult` (the
  question body, optionally the accepted answer), count on it possibly being:
  1. find the questions (`search/advanced` with a body filter), and/or
  2. pull the answers to the questions (`questions/{ids}/answers` with a body filter).
  Choose the scope sensibly - at minimum return the title, URL, and a short snippet from the body;
  the accepted answer is a high-value bonus (consider it).
- `SearchResult`: `title` (the question), `url` (to the question), `snippet` (from the body/answer),
  `source="stackexchange"`, you can fill `score` from the SO question score.
- **Rate-limit**: respect HTTP 429/503 and the `Retry-After` / `backoff` field in the response.
  Without a key the quota is lower - degrade cleanly (log, return what you have).
- Use the shared httpx client. A key (if the user has one) comes from env and only raises the quota -
  it is not required.

## Acceptance criteria

- [ ] `StackExchangeProvider.search("async python", limit=5)` returns `SearchResult` with a title, a
      URL, and a meaningful snippet (not an empty body).
- [ ] The provider is zero-config, in the default set, with no need for a key.
- [ ] Rate-limit and errors handled (degradation, not a raise upward).
- [ ] Tests against **fixtures** (stored API responses): the mapping is correct; a missing body is
      pulled / handled; an empty result is handled.
- [ ] ruff-clean, async, typed.

## How to verify

```bash
python -c "import asyncio; from solocrawl.core.search.providers.stackexchange import StackExchangeProvider; \
print(asyncio.run(StackExchangeProvider().search('asyncio gather', limit=3)))"
pytest tests -k stackexchange
```

## Notes / references

- API: `https://api.stackexchange.com/2.3`, endpoint `/search/advanced`, a filter for the body
  (`withbody` or a custom filter id). Verify the current shape and quotas if you have tools.
- Watch out for the two-phase nature - without the right filter you get results with no body and the
  snippet will be empty.
