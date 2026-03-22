"""
Runtime configuration loaded from environment (and optional ``.env``).

Secrets must never be committed; use ``.env`` locally (gitignored) or injected
secrets in production. LLM calls use an **OpenAI-shaped** HTTP API
(``openai.AsyncOpenAI`` with ``base_url``). **Default:** OpenRouter
(``LLM_BASE_URL`` → ``https://openrouter.ai/api/v1``). **Alternatively:** point
``LLM_BASE_URL`` at any other OpenAI-compatible service (direct OpenAI, Azure,
Ollama, …) — see ``docs/llm-configuration.md``.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded via ``pydantic-settings``.

    Attributes correspond to documented environment variables; see ``.env.example``.

    Notes
    -----
    ``LLM_API_KEY`` (or legacy ``OPENROUTER_API_KEY``), ``CHAT_MODEL_ID``, and
    ``EMBEDDING_MODEL_ID`` are required at runtime. The embedding vector dimension
    in the database must match the configured ``EMBEDDING_MODEL_ID`` output (see
    ``docs/llm-configuration.md`` and ``EMBEDDING_VECTOR_DIMENSIONS``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        ...,
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )
    slack_bot_token: SecretStr = Field(..., validation_alias="SLACK_BOT_TOKEN")
    slack_signing_secret: SecretStr = Field(..., validation_alias="SLACK_SIGNING_SECRET")

    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")

    openrouter_api_key: SecretStr = Field(
        ...,
        validation_alias=AliasChoices("LLM_API_KEY", "OPENROUTER_API_KEY"),
        description="API key for the OpenAI-compatible LLM endpoint (OpenRouter by default).",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENROUTER_BASE_URL"),
        description="Base URL for chat and embedding APIs (OpenRouter, OpenAI, Azure, Ollama, …).",
    )
    openrouter_http_referer: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_HTTP_REFERER", "OPENROUTER_HTTP_REFERER"),
        description="Optional Referer header (OpenRouter attribution).",
    )
    openrouter_app_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_APP_NAME", "OPENROUTER_APP_NAME"),
        description="Optional X-Title header (OpenRouter attribution).",
    )

    chat_model_id: str = Field(..., validation_alias="CHAT_MODEL_ID")
    embedding_model_id: str = Field(..., validation_alias="EMBEDDING_MODEL_ID")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    onboarding_history_per_channel_chars: int = Field(
        default=80_000,
        validation_alias="FOREST_ONBOARDING_HISTORY_PER_CHANNEL_CHARS",
        description="Max characters of message text per channel/thread in onboarding LLM prompt",
    )
    onboarding_history_total_chars: int = Field(
        default=240_000,
        validation_alias="FOREST_ONBOARDING_HISTORY_TOTAL_CHARS",
        description="Max total transcript characters across all channels for onboarding",
    )
    onboarding_history_oldest_first: bool = Field(
        default=False,
        validation_alias="FOREST_ONBOARDING_HISTORY_OLDEST_FIRST",
        description="If true, fill transcript budget from oldest messages first",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached :class:`Settings` instance (singleton per process).

    Returns
    -------
    Settings
        Parsed configuration from the environment.

    Notes
    -----
    Because this is LRU-cached, tests that need different env values should either
    set environment variables before any import of modules that call
    ``get_settings()``, or restart the interpreter / clear the cache (not typical).
    """
    return Settings()
