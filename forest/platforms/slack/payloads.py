"""
Map Slack message events to canonical :class:`~forest.integrations.types.IngestPayload`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from forest.integrations.types import AttachmentRef, ChatLine, IngestPayload
from forest.services.ingest import extract_urls

_log = logging.getLogger(__name__)


def _permalink_for_file(f: dict[str, Any]) -> str:
    """Best available URL for a Slack file: prefer permalink over url_private."""
    return f.get("permalink") or f.get("url_private") or ""


def _ts_to_datetime(ts: str) -> datetime:
    """Convert a Slack ``ts`` string (Unix epoch with fractional seconds) to UTC datetime."""
    return datetime.fromtimestamp(float(ts), tz=UTC)


async def _fetch_context_lines(
    client: AsyncWebClient,
    channel_id: str,
    message_ts: str,
    *,
    thread_ts: str | None = None,
    limit: int = 8,
) -> list[ChatLine]:
    """
    Fetch recent messages before *message_ts* for ingest context.

    Uses ``conversations.replies`` when in a thread, otherwise ``conversations.history``.
    """
    lines: list[ChatLine] = []
    try:
        if thread_ts and thread_ts != message_ts:
            resp = await client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=limit + 1,
                latest=message_ts,
                inclusive=False,
            )
        else:
            resp = await client.conversations_history(
                channel=channel_id,
                limit=limit,
                latest=message_ts,
                inclusive=False,
            )
        messages = resp.get("messages", [])
        for m in messages:
            if m.get("ts") == message_ts:
                continue
            text = (m.get("text") or "").strip()
            if not text:
                continue
            lines.append(
                ChatLine(
                    author_display=m.get("user", "unknown"),
                    text=text[:1500],
                )
            )
    except Exception:
        _log.warning(
            "could not read channel history for context",
            extra={
                "operation": "ingest_context",
                "channel_id": channel_id,
            },
        )

    lines.reverse()
    return lines[-limit:]


def build_backfill_payload(
    message: dict[str, Any],
    *,
    team_id: str,
    channel_id: str,
    channel_name: str,
) -> IngestPayload | None:
    """
    Build an ingest payload from a historical Slack message (no API calls).

    Unlike :func:`build_ingest_payload`, this does not fetch surrounding
    context from the Slack API — the message stands on its own during backfill.
    Returns ``None`` when the message has no files or URLs worth ingesting.
    """
    text = message.get("text") or ""
    link_urls = extract_urls(text)

    attachments: list[AttachmentRef] = []
    for f in message.get("files", []):
        url = _permalink_for_file(f)
        if not url:
            continue
        attachments.append(
            AttachmentRef(
                filename=f.get("name") or f.get("title") or "attachment",
                url=url,
                content_type=f.get("mimetype"),
                size=f.get("size"),
            )
        )

    if not attachments and not link_urls:
        return None

    message_ts = message.get("ts") or ""
    permalink = f"https://slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}"

    return IngestPayload(
        workspace_key=team_id,
        platform="slack",
        channel_id=channel_id,
        channel_label=channel_name,
        message_id=message_ts,
        message_url=permalink,
        author_display=message.get("user") or "unknown",
        posted_at=_ts_to_datetime(message_ts) if message_ts else datetime.now(tz=UTC),
        message_text=text,
        attachments=attachments,
        link_urls=link_urls,
        context_lines=[],
    )


async def build_ingest_payload(
    event: dict[str, Any],
    *,
    team_id: str,
    client: AsyncWebClient,
    history_limit: int = 8,
) -> IngestPayload | None:
    """
    Build an ingest payload from a Slack ``message`` event.

    Returns ``None`` when there are no attachments and no URLs to ingest.
    """
    text = event.get("text") or ""
    link_urls = extract_urls(text)

    attachments: list[AttachmentRef] = []
    for f in event.get("files", []):
        url = _permalink_for_file(f)
        if not url:
            continue
        attachments.append(
            AttachmentRef(
                filename=f.get("name") or f.get("title") or "attachment",
                url=url,
                content_type=f.get("mimetype"),
                size=f.get("size"),
            )
        )

    if not attachments and not link_urls:
        return None

    channel_id = event.get("channel") or ""
    message_ts = event.get("ts") or ""
    thread_ts = event.get("thread_ts")

    context_lines = await _fetch_context_lines(
        client,
        channel_id,
        message_ts,
        thread_ts=thread_ts,
        limit=history_limit,
    )
    # Small pause to avoid back-to-back Slack API calls from the same event
    await asyncio.sleep(0.1)

    channel_name = event.get("channel_name") or channel_id
    permalink = f"https://slack.com/archives/{channel_id}/p{message_ts.replace('.', '')}"

    return IngestPayload(
        workspace_key=team_id,
        platform="slack",
        channel_id=channel_id,
        channel_label=channel_name,
        message_id=message_ts,
        message_url=permalink,
        author_display=event.get("user") or "unknown",
        posted_at=_ts_to_datetime(message_ts) if message_ts else datetime.now(tz=UTC),
        message_text=text,
        attachments=attachments,
        link_urls=link_urls,
        context_lines=context_lines,
    )
