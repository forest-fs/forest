"""
Harvest Slack channel message history for onboarding / folder-tree LLM prompts.

Lists accessible channels via ``conversations.list``, paginates history per channel
with ``conversations.history``, and builds capped plaintext excerpts for the LLM.
Respects per-channel and total character budgets from settings.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

_log = logging.getLogger(__name__)

_RATE_LIMIT_PAUSE = 1.2


@dataclass(frozen=True)
class HistoricalMessage:
    """A raw Slack message with files or URLs, collected for backfill ingest."""

    channel_id: str
    channel_name: str
    message: dict[str, Any]


@dataclass(frozen=True)
class OnboardingChannelHistory:
    """One channel digest for the onboarding LLM prompt."""

    channel: str
    excerpt: str
    messages_scanned: int
    truncated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "excerpt": self.excerpt,
            "messages_scanned": self.messages_scanned,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class OnboardingScanResult:
    """Full workspace scan: ordered channel labels and per-channel digests."""

    channel_names: list[str]
    histories: list[OnboardingChannelHistory]
    backfill_messages: list[HistoricalMessage]

    def histories_as_json(self) -> list[dict[str, Any]]:
        return [h.as_dict() for h in self.histories]


async def _list_channels(client: AsyncWebClient) -> list[dict[str, Any]]:
    """Paginate ``conversations.list`` to get all public channels the bot can see."""
    channels: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        resp = await client.conversations_list(
            types="public_channel",
            exclude_archived=True,
            limit=200,
            cursor=cursor or "",
        )
        channels.extend(resp.get("channels", []))
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
        await asyncio.sleep(_RATE_LIMIT_PAUSE)
    return channels


_URL_RE = __import__("re").compile(r"https?://[^\s<>\"]+", __import__("re").IGNORECASE)


async def _fetch_channel_history(
    client: AsyncWebClient,
    channel_id: str,
    *,
    char_budget: int,
    oldest_first: bool,
) -> tuple[list[str], int, bool, list[dict[str, Any]]]:
    """
    Fetch messages from a channel up to *char_budget* characters.

    Returns (lines, message_count, truncated, messages_with_assets).
    The last element contains raw message dicts that have files or URLs.
    """
    parts: list[str] = []
    asset_msgs: list[dict[str, Any]] = []
    used = 0
    count = 0
    truncated = False
    cursor: str | None = None

    while True:
        resp = await client.conversations_history(
            channel=channel_id,
            limit=200,
            cursor=cursor or "",
        )
        messages = resp.get("messages", [])
        if oldest_first:
            messages = list(reversed(messages))

        for msg in messages:
            if msg.get("subtype"):
                continue
            count += 1
            user_name = msg.get("user", "unknown")
            text = (msg.get("text") or "").strip()
            files = msg.get("files", [])

            has_files = bool(files)
            has_urls = bool(_URL_RE.search(text)) if text else False
            if has_files or has_urls:
                asset_msgs.append(msg)

            if files:
                att_note = f"[{len(files)} attachment(s)]"
                text = f"{text} {att_note}".strip() if text else att_note
            if not text:
                continue
            line = f"{user_name}: {text}\n"
            if used + len(line) > char_budget:
                truncated = True
                return parts, count, truncated, asset_msgs
            parts.append(line)
            used += len(line)

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
        await asyncio.sleep(_RATE_LIMIT_PAUSE)

    return parts, count, truncated, asset_msgs


async def collect_channel_histories_for_onboarding(
    client: AsyncWebClient,
    *,
    per_channel_char_budget: int,
    total_char_budget: int,
    oldest_first: bool = False,
) -> OnboardingScanResult:
    """
    Read accessible channels and build capped text excerpts for onboarding.

    Parameters
    ----------
    client : AsyncWebClient
        Authenticated Slack API client.
    per_channel_char_budget : int
        Max transcript characters per channel.
    total_char_budget : int
        Max combined transcript characters across all channels.
    oldest_first : bool, optional
        If true, fill budget from oldest messages first; default newest first.
    """
    raw_channels = await _list_channels(client)
    raw_channels.sort(key=lambda c: c.get("name", ""))

    channel_names = [ch.get("name", ch["id"]) for ch in raw_channels]
    histories: list[OnboardingChannelHistory] = []
    all_backfill: list[HistoricalMessage] = []
    total_used = 0
    total_messages = 0

    for ch in raw_channels:
        label = ch.get("name", ch["id"])
        channel_id = ch["id"]

        if not ch.get("is_member", False):
            try:
                await client.conversations_join(channel=channel_id)
                _log.info("auto-joined channel %s (%s)", label, channel_id)
            except Exception:
                _log.warning(
                    "could not auto-join channel %s (%s), skipping",
                    label, channel_id, exc_info=True,
                )
                histories.append(
                    OnboardingChannelHistory(
                        channel=label,
                        excerpt="[could not join channel]",
                        messages_scanned=0,
                        truncated=False,
                    )
                )
                continue

        remaining_global = total_char_budget - total_used
        remaining_budget = min(per_channel_char_budget, remaining_global)
        if remaining_budget <= 0:
            histories.append(
                OnboardingChannelHistory(
                    channel=label,
                    excerpt="[skipped: global transcript budget exhausted]",
                    messages_scanned=0,
                    truncated=True,
                )
            )
            continue

        try:
            parts, count, truncated, asset_msgs = await _fetch_channel_history(
                client,
                channel_id,
                char_budget=remaining_budget,
                oldest_first=oldest_first,
            )
        except Exception:
            _log.exception(
                "onboarding scan channel failed",
                extra={
                    "operation": "onboarding_scan",
                    "channel": label,
                    "channel_id": channel_id,
                },
            )
            histories.append(
                OnboardingChannelHistory(
                    channel=label,
                    excerpt="[error while reading history; see logs]",
                    messages_scanned=0,
                    truncated=True,
                )
            )
            continue

        for raw_msg in asset_msgs:
            all_backfill.append(
                HistoricalMessage(
                    channel_id=channel_id,
                    channel_name=label,
                    message=raw_msg,
                )
            )

        excerpt = "".join(parts)
        if truncated:
            excerpt += (
                f"\n[...history truncated: {count} messages read; "
                f"budget {remaining_budget} chars...]"
            )
        if not excerpt.strip():
            excerpt = "[no text content in readable history]"

        total_used += len(excerpt)
        total_messages += count
        histories.append(
            OnboardingChannelHistory(
                channel=label,
                excerpt=excerpt,
                messages_scanned=count,
                truncated=truncated,
            )
        )
        await asyncio.sleep(_RATE_LIMIT_PAUSE)

    _log.info(
        "onboarding history scan complete",
        extra={
            "operation": "onboarding_scan",
            "channels": len(channel_names),
            "messages": total_messages,
            "transcript_chars": total_used,
            "backfill_candidates": len(all_backfill),
        },
    )
    return OnboardingScanResult(
        channel_names=channel_names,
        histories=histories,
        backfill_messages=all_backfill,
    )
