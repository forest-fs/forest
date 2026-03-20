"""
Map ``discord.py`` messages to canonical :class:`~forest.integrations.types.IngestPayload`.
"""

from __future__ import annotations

import logging

import discord

from forest.integrations.types import AttachmentRef, ChatLine, IngestPayload
from forest.services.ingest import extract_urls

_log = logging.getLogger(__name__)


async def build_ingest_payload(
    message: discord.Message,
    *,
    history_limit: int = 8,
) -> IngestPayload | None:
    """
    Build an ingest payload when a guild message has attachments or extractable URLs.

    Parameters
    ----------
    message : discord.Message
        Discord gateway message (must be in a guild for MVP ingest).
    history_limit : int, optional
        Max prior messages to include as ``context_lines`` (fetched before this message).

    Returns
    -------
    IngestPayload or None
        ``None`` for DMs, messages without guild, or when there are no attachments
        and no URLs in content.

    Notes
    -----
    History reads are best-effort; :exc:`discord.Forbidden` results in empty context
    with a WARNING log (missing history intent or channel permissions).
    """
    if not message.guild:
        return None
    link_urls = extract_urls(message.content or "")
    attachments: list[AttachmentRef] = []
    for a in message.attachments:
        attachments.append(
            AttachmentRef(
                filename=a.filename or "attachment",
                url=a.url,
                content_type=a.content_type,
                size=a.size,
            )
        )
    if not attachments and not link_urls:
        return None

    context_lines: list[ChatLine] = []
    if isinstance(message.channel, discord.TextChannel):
        try:
            async for m in message.channel.history(limit=history_limit, before=message.created_at):
                text = (m.content or "").strip()
                if not text and not m.attachments:
                    continue
                context_lines.append(
                    ChatLine(author_display=str(m.author.display_name), text=text[:1500])
                )
        except discord.Forbidden:
            _log.warning(
                "could not read channel history for context",
                extra={
                    "operation": "ingest_context",
                    "guild_id": str(message.guild.id),
                    "channel_id": str(message.channel.id),
                },
            )
        context_lines.reverse()

    jump = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
    return IngestPayload(
        workspace_key=str(message.guild.id),
        platform="discord",
        channel_id=str(message.channel.id),
        channel_label=getattr(message.channel, "name", None) or str(message.channel.id),
        message_id=str(message.id),
        message_url=jump,
        author_display=str(message.author.display_name),
        posted_at=message.created_at,
        message_text=message.content or "",
        attachments=attachments,
        link_urls=link_urls,
        context_lines=context_lines,
    )
