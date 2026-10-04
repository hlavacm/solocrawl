"""Package provider registration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from solocrawl.core.packages.protocol import PackageProvider

ProviderFactory = Callable[..., PackageProvider]
ProviderType = TypeVar("ProviderType", bound=PackageProvider)


@dataclass(frozen=True)
class ProviderRegistration:
    """Metadata for a registered package provider."""

    name: str
    ecosystem: str
    zero_config: bool
    required_env_key: str | None
    factory: ProviderFactory
    configurable: bool = False


_REGISTRY: dict[str, ProviderRegistration] = {}


def register(
    name: str,
    *,
    ecosystem: str,
    zero_config: bool = False,
    required_env_key: str | None = None,
    configurable: bool = False,
) -> Callable[[type[ProviderType]], type[ProviderType]]:
    """Register a package provider class under a stable name."""

    def decorator(cls: type[ProviderType]) -> type[ProviderType]:
        if name in _REGISTRY:
            msg = f"package provider already registered: {name!r}"
            raise ValueError(msg)

        registration = ProviderRegistration(
            name=name,
            ecosystem=ecosystem,
            zero_config=zero_config,
            required_env_key=required_env_key,
            factory=cls,
            configurable=configurable,
        )
        _REGISTRY[name] = registration

        cls.name = name  # type: ignore[attr-defined]
        cls.ecosystem = ecosystem  # type: ignore[attr-defined]
        cls.zero_config = zero_config  # type: ignore[attr-defined]

        return cls

    return decorator


def get_registration(name: str) -> ProviderRegistration | None:
    """Return registration metadata for a provider name, if present."""

    return _REGISTRY.get(name)


def get_registration_for_ecosystem(ecosystem: str) -> ProviderRegistration | None:
    """Return the first registered provider for an ecosystem."""

    for registration in _REGISTRY.values():
        if registration.ecosystem == ecosystem:
            return registration
    return None


def list_registrations() -> tuple[ProviderRegistration, ...]:
    """Return all registered package providers."""

    return tuple(_REGISTRY.values())


def clear_registry() -> None:
    """Remove all registrations. Intended for tests only."""

    _REGISTRY.clear()
