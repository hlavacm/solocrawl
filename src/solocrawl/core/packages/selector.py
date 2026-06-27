"""Select which package providers are available for a configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping

from solocrawl.config import Config, init_env
from solocrawl.core.packages.protocol import PackageProvider
from solocrawl.core.packages.registry import list_registrations


def select_providers(
    config: Config,
    *,
    env: Mapping[str, str] | None = None,
) -> list[PackageProvider]:
    """Return package provider instances enabled for the configuration."""
    if env is None:
        init_env()
    source = os.environ if env is None else env
    selected: list[PackageProvider] = []

    for registration in list_registrations():
        if registration.zero_config:
            selected.append(registration.factory())
            continue

        if registration.name not in config.enabled_providers:
            continue

        if registration.required_env_key is not None:
            key_value = source.get(registration.required_env_key)
            if key_value is None or key_value.strip() == "":
                continue

        selected.append(registration.factory())

    return selected


def select_provider_for_ecosystem(
    ecosystem: str,
    config: Config,
    *,
    env: Mapping[str, str] | None = None,
) -> PackageProvider | None:
    """Return the enabled provider for a specific ecosystem, if any."""
    normalized = ecosystem.strip().lower()
    for provider in select_providers(config, env=env):
        if provider.ecosystem == normalized:
            return provider
    return None
