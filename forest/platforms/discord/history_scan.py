"""
Harvest readable guild message history for onboarding / folder-tree LLM prompts.

Walks every text channel (and active forum post threads) the bot can access, iterates
**all** messages via Discord pagination, and builds capped plaintext excerpts for the
chat model. Caps avoid blowing LLM context on huge guilds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import discord

_log = logging.getLogger(__name__)


def _channel_label(channel: discord.abc.GuildChannel | discord.Thread) -> str:
    """Stable human-readable label for transcript headers (unique enough for the LLM)."""
    if isinstance(channel, discord.Thread):
        parent = channel.parent
        if parent and hasattr(parent, "name"):
            return f"{parent.name}/{channel.name}"
        return channel.name
    return channel.name


def _iter_scannable_channels(guild: discord.Guild) -> list[discord.abc.Messageable]:
    """
    Text channels and active threads under forum channels, ordered by guild layout.

    Notes
    -----
    Archived forum threads are not walked (extra API surface); only ``guild.channels``
    order plus forum ``threads``.
    """
    ordered: list[discord.abc.Messageable] = []
    for ch in sorted(guild.channels, key=lambda c: (getattr(c, "position", 0), c.id)):
        if isinstance(ch, discord.TextChannel):
            ordered.append(ch)
        elif isinstance(ch, discord.ForumChannel):
            for th in sorted(ch.threads, key=lambda t: t.id):
                ordered.append(th)
    return ordered


@dataclass(frozen=True)
class OnboardingChannelHistory:
    """One channel or thread digest passed to :meth:`~forest.services.llm.service.LLMService.generate_base_tree`."""

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
    """Full guild scan: ordered labels (for hints) and per-channel digests."""

    channel_names: list[str]
    histories: list[OnboardingChannelHistory]

    def histories_as_json(self) -> list[dict[str, Any]]:
        return [h.as_dict() for h in self.histories]


async def collect_channel_histories_for_onboarding(
    guild: discord.Guild,
    *,
    per_channel_char_budget: int,
    total_char_budget: int,
    oldest_first: bool = False,
) -> OnboardingScanResult:
    """
    Read every accessible message in text channels and active forum threads, building
    capped excerpts for the onboarding LLM.

    Parameters
    ----------
    guild : discord.Guild
        Target server.
    per_channel_char_budget : int
        Max characters of transcript text per channel/thread (after skipping
        unreadable channels).
    total_char_budget : int
        Max combined transcript characters across all excerpts (remaining budget is
        split across later channels).
    oldest_first : bool, optional
        If true, walk history from oldest to newest; default is newest first (recent
        context fills the budget first).

    Returns
    -------
    OnboardingScanResult
        Channel labels and digest rows suitable for JSON in the LLM user message.
    """
    me = guild.me
    if me is None:
        _log.warning(
            "onboarding scan skipped: guild.me is None",
            extra={"operation": "onboarding_scan", "guild_id": str(guild.id)},
        )
        return OnboardingScanResult(channel_names=[], histories=[])

    targets = _iter_scannable_channels(guild)
    channel_names = [_channel_label(ch) for ch in targets]
    histories: list[OnboardingChannelHistory] = []
    total_used = 0
    total_messages = 0

    for channel in targets:
        label = _channel_label(channel)
        perms = channel.permissions_for(me)
        if not perms.read_messages or not perms.read_message_history:
            histories.append(
                OnboardingChannelHistory(
                    channel=label,
                    excerpt="[bot cannot read messages in this channel]",
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

        parts: list[str] = []
        used = 0
        count = 0
        truncated = False

        try:
            async for msg in channel.history(limit=None, oldest_first=oldest_first):  # type: ignore[union-attr]
                count += 1
                author = getattr(msg.author, "display_name", None) or str(msg.author)
                body = (msg.clean_content or "").strip()
                if msg.attachments:
                    att_note = f"[{len(msg.attachments)} attachment(s)]"
                    body = f"{body} {att_note}".strip() if body else att_note
                if not body:
                    continue
                line = f"{author}: {body}\n"
                if used + len(line) > remaining_budget:
                    truncated = True
                    break
                parts.append(line)
                used += len(line)
        except discord.Forbidden:
            histories.append(
                OnboardingChannelHistory(
                    channel=label,
                    excerpt="[forbidden: could not read history]",
                    messages_scanned=count,
                    truncated=True,
                )
            )
            continue
        except Exception:
            _log.exception(
                "onboarding scan channel failed",
                extra={
                    "operation": "onboarding_scan",
                    "guild_id": str(guild.id),
                    "channel": label,
                },
            )
            histories.append(
                OnboardingChannelHistory(
                    channel=label,
                    excerpt="[error while reading history; see logs]",
                    messages_scanned=count,
                    truncated=True,
                )
            )
            continue

        excerpt = "".join(parts)
        if truncated:
            excerpt += (
                f"\n[...history truncated: {count} messages read in this channel; "
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

    _log.info(
        "onboarding history scan complete",
        extra={
            "operation": "onboarding_scan",
            "guild_id": str(guild.id),
            "channels": len(channel_names),
            "messages": total_messages,
            "transcript_chars": total_used,
        },
    )
    return OnboardingScanResult(channel_names=channel_names, histories=histories)
