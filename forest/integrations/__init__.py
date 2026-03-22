"""
Platform-neutral DTOs (no SDK types).

Adapters map native events into these models before calling core services.
"""

from forest.integrations.types import AttachmentRef, ChatLine, IngestPayload

__all__ = ["AttachmentRef", "ChatLine", "IngestPayload"]
