"""Tests for configuration loading."""

from pathlib import Path

import pytest
from dotenv import load_dotenv

from solocrawl.config import Config, ProxyMode, init_env, load_config


def test_defaults_without_env() -> None:
    config = load_config(env={})

    assert config.concurrency.max_concurrent_fetches == 10
    assert config.concurrency.per_domain_limit == 2
    assert config.concurrency.timeout_seconds == 30.0
    assert config.concurrency.max_retries == 3
    assert config.proxy.enabled is False
    assert config.proxy.mode is ProxyMode.LIST
    assert config.proxy.proxies == ()
    assert config.proxy.endpoint is None
    assert config.browser.allowed is True
    assert config.fetch.allow_internal_urls is False
    assert config.fetch.user_agent is None
    assert config.enabled_providers == frozenset()


def test_env_overrides_defaults() -> None:
    env = {
        "SOLOCRAWL_MAX_CONCURRENCY": "25",
        "SOLOCRAWL_PER_DOMAIN_LIMIT": "5",
        "SOLOCRAWL_TIMEOUT_SECONDS": "45.5",
        "SOLOCRAWL_MAX_RETRIES": "1",
        "SOLOCRAWL_PROXY_ENABLED": "true",
        "SOLOCRAWL_PROXY_MODE": "endpoint",
        "SOLOCRAWL_PROXY_ENDPOINT": "http://proxy.example:8080",
        "SOLOCRAWL_PROXY_USERNAME": "user",
        "SOLOCRAWL_PROXY_PASSWORD": "secret",
        "SOLOCRAWL_BROWSER_ALLOWED": "false",
    }

    config = load_config(env=env)

    assert config.concurrency.max_concurrent_fetches == 25
    assert config.concurrency.per_domain_limit == 5
    assert config.concurrency.timeout_seconds == 45.5
    assert config.concurrency.max_retries == 1
    assert config.proxy.enabled is True
    assert config.proxy.mode is ProxyMode.ENDPOINT
    assert config.proxy.endpoint == "http://proxy.example:8080"
    assert config.proxy.username == "user"
    assert config.proxy.password == "secret"
    assert config.browser.allowed is False


def test_enabled_providers_parsing() -> None:
    config = load_config(
        env={"SOLOCRAWL_ENABLE_PROVIDERS": " arxiv, hackernews ,pubmed "},
    )

    assert config.enabled_providers == frozenset({"arxiv", "hackernews", "pubmed"})


def test_proxy_list_parsing() -> None:
    config = load_config(
        env={
            "SOLOCRAWL_PROXY_ENABLED": "1",
            "SOLOCRAWL_PROXY_LIST": "http://a:1, http://b:2",
        },
    )

    assert config.proxy.proxies == ("http://a:1", "http://b:2")


def test_load_config_uses_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOLOCRAWL_MAX_CONCURRENCY", "7")

    config = load_config()

    assert config.concurrency.max_concurrent_fetches == 7


def test_fetch_config_from_env() -> None:
    config = load_config(
        env={
            "SOLOCRAWL_ALLOW_INTERNAL_URLS": "true",
            "SOLOCRAWL_USER_AGENT": "CustomBot/9.9",
        },
    )

    assert config.fetch.allow_internal_urls is True
    assert config.fetch.user_agent == "CustomBot/9.9"


def test_respect_robots_defaults_true_and_opts_out() -> None:
    assert load_config(env={}).fetch.respect_robots is True
    assert load_config(env={"SOLOCRAWL_RESPECT_ROBOTS": "false"}).fetch.respect_robots is False


def test_cache_ttl_defaults_zero_and_parses_env() -> None:
    assert load_config(env={}).fetch.cache_ttl_seconds == 0
    assert load_config(env={"SOLOCRAWL_CACHE_TTL_SECONDS": "3600"}).fetch.cache_ttl_seconds == 3600


def test_config_is_frozen() -> None:
    config = Config()
    with pytest.raises(AttributeError):
        config.browser.allowed = False  # type: ignore[misc]


def test_init_env_loads_dotenv_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOLOCRAWL_MAX_CONCURRENCY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SOLOCRAWL_MAX_CONCURRENCY=42\n", encoding="utf-8")

    load_dotenv(env_file)

    config = load_config()

    assert config.concurrency.max_concurrent_fetches == 42


def test_shell_env_overrides_dotenv_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SOLOCRAWL_MAX_CONCURRENCY=42\n", encoding="utf-8")
    monkeypatch.setenv("SOLOCRAWL_MAX_CONCURRENCY", "99")

    load_dotenv(env_file)

    config = load_config()

    assert config.concurrency.max_concurrent_fetches == 99


def test_init_env_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOLOCRAWL_MAX_CONCURRENCY", raising=False)

    init_env()
    init_env()

    config = load_config()

    assert config.concurrency.max_concurrent_fetches == 10
