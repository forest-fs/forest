"""
LLM integration: single OpenRouter (OpenAI-compatible) client for chat and embeddings.

Application code must not add alternate vendor SDKs in the MVP; models are selected via
OpenRouter slugs in settings.
"""

from forest.services.llm.service import LLMService

__all__ = ["LLMService"]
