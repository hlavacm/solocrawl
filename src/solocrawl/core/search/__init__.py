"""Federated web search across pluggable providers."""

from solocrawl.core.search.federation import federated_search
from solocrawl.core.search.fusion import RRF_K, fuse_results, normalize_url
from solocrawl.core.search.protocol import SearchProvider
from solocrawl.core.search.registry import (
    ProviderRegistration,
    clear_registry,
    get_registration,
    list_registrations,
    register,
)
from solocrawl.core.search.selector import select_providers

__all__ = [
    "ProviderRegistration",
    "RRF_K",
    "SearchProvider",
    "clear_registry",
    "federated_search",
    "fuse_results",
    "get_registration",
    "list_registrations",
    "normalize_url",
    "register",
    "select_providers",
]
