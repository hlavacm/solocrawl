# Feature 16: Opt-in search providers

## Goal

Add four opt-in search providers sharing the same interface as the default set: Wikidata, Hacker News
(Algolia), arXiv, PubMed/NCBI. Disabled by default, activated via configuration.

## Context

Demonstrates the strength of the plugin architecture - extension with specialized sources without
touching the core (see `architecture.md`, `ROADMAP.md`). These sources are valuable for specific
queries (facts, academic, dev, biomed), but do not belong in the default set, so the first impression
stays clean and fast.

## Dependencies

- Requires done: 04 (interface), 06 (federation - so they can be combined with the default)
- Blocks: -

## Scope

Belongs here: four providers, each `zero_config=False` (opt-in), mapping to `SearchResult`, tests
against fixtures. Does not belong here: new package ecosystems, new core mechanisms. Feel free to
split into four separate commits (one provider = one).

## Implementation guidance

All implement `SearchProvider`, register as opt-in, are activated via config (e.g.
`SOLOCRAWL_ENABLE_PROVIDERS=arxiv,hackernews,...`). All degrade cleanly (log, do not raise upward).

- **Wikidata**: structured facts (entities). REST/SPARQL or `wbsearchentities`. Return the entity,
  the description, the URL. A complement to Wikipedia for structured lookup.
- **Hacker News (Algolia)**: `https://hn.algolia.com/api/v1/search`. No key, fast. Return the title,
  URL (to the post/discussion), optionally the score/comments as `score`/snippet.
- **arXiv**: the official arXiv API (Atom feed). Return the title, the abstract (snippet), the URL to
  the preprint. High value for the AI/ML/physics audience.
- **PubMed/NCBI**: E-utilities (`esearch` + `esummary`/`efetch`). Works without a key (a key only
  raises the rate limit). Return the title, abstract/snippet, URL. Respect NCBI rate-limit rules.

For each: respect the `limit`, handle errors/rate-limit, use the shared httpx client.

## Acceptance criteria

- [ ] All four providers implement the interface and are registered as opt-in (not in the default).
- [ ] Activation via config includes them in the selector and thus in federation.
- [ ] Each returns normalized `SearchResult`; errors/rate-limit handled (degradation).
- [ ] Tests against **fixtures** for each provider (mapping, empty/error state).
- [ ] ruff-clean, async, typed.

## How to verify

```bash
SOLOCRAWL_ENABLE_PROVIDERS=arxiv,hackernews solocrawl search "transformer attention" --limit 6
pytest tests -k "wikidata or hackernews or arxiv or pubmed"
```

## Notes / references

- Hacker News Algolia: `http://hn.algolia.com/api/v1/search`
- arXiv API: `http://export.arxiv.org/api/query`
- PubMed E-utilities: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- Wikidata: the `wbsearchentities` action API / the SPARQL endpoint
- Verify the current shapes if you have tools. These change less than scraping sources, but still.
