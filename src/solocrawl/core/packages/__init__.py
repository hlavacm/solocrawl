"""Package version lookup across official registries."""

from solocrawl.core.packages.protocol import PackageProvider
from solocrawl.core.packages.registry import (
    ProviderRegistration,
    clear_registry,
    get_registration,
    get_registration_for_ecosystem,
    list_registrations,
    register,
)
from solocrawl.core.packages.resolver import VersionEntry, previous_versions, resolve_latest
from solocrawl.core.packages.selector import select_provider_for_ecosystem, select_providers

__all__ = [
    "PackageProvider",
    "ProviderRegistration",
    "VersionEntry",
    "clear_registry",
    "get_registration",
    "get_registration_for_ecosystem",
    "list_registrations",
    "previous_versions",
    "register",
    "resolve_latest",
    "select_provider_for_ecosystem",
    "select_providers",
]
