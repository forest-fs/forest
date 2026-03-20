"""
Canonical ingest types consumed by onboarding and the ingest pipeline.

These models intentionally avoid any chat-SDK imports so ``forest.services`` can
stay platform-agnostic.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AttachmentRef(BaseModel):
    """
    Reference to an uploaded attachment (URL and metadata only; no bytes stored).

    Attributes
    ----------
    filename : str
        Original filename as reported by the platform.
    url : str
        HTTPS URL suitable for retrieval or citation.
    content_type : str or None
        MIME type when available.
    size : int or None
        Size in bytes when available.
    """

    filename: str
    url: str
    content_type: str | None = None
    size: int | None = None


class ChatLine(BaseModel):
    """
    One line of contextual chat transcript prior to the ingested message.

    Attributes
    ----------
    author_display : str
        Human-readable author label (display name).
    text : str
        Message text, possibly truncated by the adapter.
    """

    author_display: str
    text: str


class IngestPayload(BaseModel):
    """
    Everything needed to route, summarize, and persist one chat message's cues.

    Attributes
    ----------
    workspace_key : str
        External workspace id (Discord guild id string in the MVP).
    platform : {'discord'}
        Source platform literal for future expansion.
    channel_id, channel_label : str
        Channel identity and human label for logging / prompts.
    message_id, message_url : str
        Stable message id and jump URL for dedup and UI links.
    author_display : str
        Who posted the message.
    posted_at : datetime
        Message timestamp (timezone-aware from Discord).
    message_text : str
        Plain text body (may be empty if attachments-only).
    attachments : list of AttachmentRef
        Files attached to the message.
    link_urls : list of str
        HTTP(S) URLs extracted from ``message_text``.
    context_lines : list of ChatLine
        Recent channel history before ``posted_at`` (newest last after adapter prep).

    Notes
    -----
    The ingest service expands ``attachments`` and ``link_urls`` into separate
    routing + embedding calls (one DB transaction per cue).
    """

    workspace_key: str = Field(..., description="Platform workspace id (e.g. Discord guild id)")
    platform: Literal["discord"] = "discord"
    channel_id: str
    channel_label: str
    message_id: str
    message_url: str
    author_display: str
    posted_at: datetime
    message_text: str
    attachments: list[AttachmentRef] = Field(default_factory=list)
    link_urls: list[str] = Field(default_factory=list)
    context_lines: list[ChatLine] = Field(default_factory=list)
