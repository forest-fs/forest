"""
Pytest configuration: default env vars so imports of ``forest.config`` succeed.

Real secrets are not required for unit tests; integration tests opt in separately.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://forest:forest@127.0.0.1:5432/forest",
)
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("CHAT_MODEL_ID", "openai/gpt-4o-mini")
os.environ.setdefault("EMBEDDING_MODEL_ID", "openai/text-embedding-3-small")
