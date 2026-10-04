"""Select which search providers to run for a given configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping

from solocrawl.config import Config, init_env
from solocrawl.core.search.protocol import SearchProvider
from solocrawl.core.search.registry import list_registrations


def select_providers(
    config: Config,
    *,
    env: Mapping[str, str] | None = None,
) -> list[SearchProvider]:
    """Return provider instances enabled for the given configuration.

    Zero-config providers are always included. Opt-in providers are included when
    listed in ``config.enabled_providers`` and, if they require an API key, when
    that key is present in the environment.
    """
    if env is None:
        init_env()
    source = os.environ if env is None else env
    selected: list[SearchProvider] = []

    for registration in list_registrations():
        if registration.zero_config:
            selected.append(
                registration.factory(config=config)
                if registration.configurable
                else registration.factory()
            )
            continue

        if registration.name not in config.enabled_providers:
            continue

        if registration.required_env_key is not None:
            key_value = source.get(registration.required_env_key)
            if key_value is None or key_value.strip() == "":
                continue

        selected.append(
            registration.factory(config=config)
            if registration.configurable
            else registration.factory()
        )

    return selected
