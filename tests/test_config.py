"""Tests for environment-driven settings (LLM env aliases)."""

from __future__ import annotations

import pytest

from forest.config import Settings, get_settings


def _minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/forest_test")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "sig-test")
    monkeypatch.setenv("CHAT_MODEL_ID", "test-chat-model")
    monkeypatch.setenv("EMBEDDING_MODEL_ID", "test-embed-model")


def test_llm_api_key_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "secret-via-llm-key")
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.openrouter_api_key.get_secret_value() == "secret-via-llm-key"


def test_openrouter_api_key_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-via-legacy-name")
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.openrouter_api_key.get_secret_value() == "secret-via-legacy-name"


def test_llm_base_url_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.openrouter_base_url == "https://api.openai.com/v1"


def test_settings_direct_llm_aliases_without_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate pydantic alias resolution without loading a local ``.env`` file."""
    _minimal_env(monkeypatch)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "k2")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    s = Settings(_env_file=None)
    assert s.openrouter_api_key.get_secret_value() == "k2"
    assert s.openrouter_base_url == "http://localhost:11434/v1"
