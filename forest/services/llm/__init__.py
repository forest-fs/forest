"""
LLM integration: one OpenAI-compatible HTTP client for chat and embeddings.

The default ``base_url`` is OpenRouter; operators can point ``LLM_BASE_URL`` at any
compatible API (OpenAI, Azure OpenAI, Ollama, …). Application code must not add
alternate vendor SDKs in the MVP; see ``docs/llm-configuration.md``.
"""

from forest.services.llm.service import LLMService

__all__ = ["LLMService"]
