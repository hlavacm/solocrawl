"""Search provider implementations."""

from solocrawl.core.search.providers import arxiv as arxiv  # noqa: F401
from solocrawl.core.search.providers import duckduckgo as duckduckgo  # noqa: F401
from solocrawl.core.search.providers import github as github  # noqa: F401
from solocrawl.core.search.providers import hackernews as hackernews  # noqa: F401
from solocrawl.core.search.providers import mdn as mdn  # noqa: F401
from solocrawl.core.search.providers import pubmed as pubmed  # noqa: F401
from solocrawl.core.search.providers import searxng as searxng  # noqa: F401
from solocrawl.core.search.providers import stackexchange as stackexchange  # noqa: F401
from solocrawl.core.search.providers import wikidata as wikidata  # noqa: F401
from solocrawl.core.search.providers import wikipedia as wikipedia  # noqa: F401

__all__ = [
    "arxiv",
    "duckduckgo",
    "github",
    "hackernews",
    "mdn",
    "pubmed",
    "searxng",
    "stackexchange",
    "wikidata",
    "wikipedia",
]
