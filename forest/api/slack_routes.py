"""
Slack webhook routes: Events API (``/slack/events``).

Bot mentions (``@forest init``, ``@forest show``, etc.) are handled via
``app_mention`` events — no slash commands required.

Signature verification uses HMAC-SHA256 per Slack's signing secret protocol.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Request, Response
from slack_sdk.web.async_client import AsyncWebClient

from forest.config import get_settings
from forest.db.session import session_scope
from forest.platforms.slack.history_scan import collect_channel_histories_for_onboarding
from forest.platforms.slack.payloads import build_backfill_payload, build_ingest_payload
from forest.repositories.file_node_repo import FileNodeRepository
from forest.repositories.workspace_repo import WorkspaceRepository
from forest.services.file_tree import file_nodes_to_tree_lines
from forest.services.ingest import process_ingest
from forest.services.llm.service import LLMService
from forest.services.onboarding import run_onboarding_for_workspace

_log = logging.getLogger(__name__)

router = APIRouter()

_workspace_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
    lambda: asyncio.Semaphore(2)
)

_HELP_TEXT = (
    "*Forest* captures attachments and links from this workspace "
    "into a virtual folder tree.\n\n"
    "*Commands*\n"
    "• `@forest help` — this overview\n"
    "• `@forest init` — scan readable channels and seed the folder tree via LLM "
    "(once per workspace unless you use `update`)\n"
    "• `@forest update` — same scan + re-merge new folders (keeps existing files)\n"
    "• `@forest show` — captured files as a nested list\n\n"
    "*Ingest* — During init, Forest backfills files and links from channel history. "
    "After that, new attachments and URLs are captured automatically."
)


def _verify_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify a Slack request signature (HMAC-SHA256)."""
    secret = get_settings().slack_signing_secret.get_secret_value()
    basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    computed = "v0=" + hmac.new(
        secret.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def _slack_client() -> AsyncWebClient:
    token = get_settings().slack_bot_token.get_secret_value()
    return AsyncWebClient(token=token)


async def _run_ingest(event: dict[str, Any], team_id: str) -> None:
    """Build payload and process ingest; meant to run as a background task."""
    client = _slack_client()
    payload = await build_ingest_payload(event, team_id=team_id, client=client)
    if payload is None:
        return
    llm = LLMService()
    sem = _workspace_semaphores[team_id]
    try:
        async with sem:
            await process_ingest(payload, llm)
    except Exception:
        _log.exception(
            "ingest failed",
            extra={"operation": "ingest", "workspace_key": team_id},
        )


async def _run_onboarding(
    team_id: str, *, force: bool, channel_id: str
) -> None:
    """Run onboarding and post the result back to *channel_id*."""
    settings = get_settings()
    client = _slack_client()
    llm = LLMService(settings)

    async def _reply(text: str) -> None:
        await client.chat_postMessage(channel=channel_id, text=text)

    try:
        scan = await collect_channel_histories_for_onboarding(
            client,
            per_channel_char_budget=settings.onboarding_history_per_channel_chars,
            total_char_budget=settings.onboarding_history_total_chars,
            oldest_first=settings.onboarding_history_oldest_first,
        )
    except Exception:
        _log.exception(
            "onboarding scan failed",
            extra={"operation": "onboarding_scan", "workspace_key": team_id},
        )
        await _reply("Onboarding scan failed. Check logs.")
        return

    try:
        async with session_scope() as session:
            if force:
                ws_repo = WorkspaceRepository(session)
                ws = await ws_repo.get_by_platform_ids("slack", team_id)
                if ws is None or not ws.is_initialized:
                    await _reply(
                        "Forest is not initialized yet. "
                        "Mention me with `init` first."
                    )
                    return

            did = await run_onboarding_for_workspace(
                session,
                platform="slack",
                platform_workspace_id=team_id,
                text_channel_names=scan.channel_names,
                workspace_name=None,
                llm=llm,
                force=force,
                channel_histories=scan.histories_as_json(),
            )
    except Exception:
        _log.exception(
            "onboarding failed",
            extra={"operation": "onboarding", "workspace_key": team_id},
        )
        await _reply("Onboarding failed. Check server logs.")
        return

    if force:
        msg = (
            "Folder tree refreshed. New directories from the latest layout were merged "
            "(existing files and paths were not removed)."
        )
    elif did:
        msg = "Forest initialized. Folder tree created."
    else:
        msg = "Forest is already initialized for this workspace."

    backfill_msgs = scan.backfill_messages
    if backfill_msgs:
        msg += f"\nBackfilling {len(backfill_msgs)} historical message(s) with files or links\u2026"

    await _reply(msg)

    if backfill_msgs:
        ingested = 0
        sem = _workspace_semaphores[team_id]
        for hm in backfill_msgs:
            payload = build_backfill_payload(
                hm.message,
                team_id=team_id,
                channel_id=hm.channel_id,
                channel_name=hm.channel_name,
            )
            if payload is None:
                continue
            try:
                async with sem:
                    await process_ingest(payload, llm)
                ingested += 1
            except Exception:
                _log.exception(
                    "backfill ingest failed",
                    extra={
                        "operation": "backfill",
                        "workspace_key": team_id,
                        "message_id": payload.message_id,
                    },
                )
            await asyncio.sleep(0.3)

        await _reply(f"Backfill complete \u2014 ingested {ingested} file(s) from history.")


async def _handle_show(team_id: str) -> str:
    """Load file tree and format as Slack mrkdwn."""
    async with session_scope() as session:
        ws_repo = WorkspaceRepository(session)
        files_repo = FileNodeRepository(session)
        ws = await ws_repo.get_by_platform_ids("slack", team_id)
        if ws is None or not ws.is_initialized:
            return "Forest is not initialized yet. Ask an admin to mention me with `init`."
        nodes = await files_repo.list_files_flat(ws.id)

    if not nodes:
        return "No files captured yet."

    lines = file_nodes_to_tree_lines(nodes, slack_mrkdwn_links=True)
    body = "\n".join(lines)
    intro = "Here's your workspace knowledge, organized by forest:"
    outro = "Your knowledge will be organized by forest as you continue to share files."
    max_len = 3000
    if len(body) > max_len:
        body = body[: max_len - 1].rstrip() + "…"
    return f"{intro}\n\n{body}\n\n{outro}"


async def _handle_mention(event: dict[str, Any], team_id: str) -> None:
    """Dispatch a command from an ``app_mention`` event."""
    client = _slack_client()
    channel_id = event.get("channel", "")
    raw_text = event.get("text", "")
    command = re.sub(r"<@[^>]+>", "", raw_text).strip().lower()

    _log.info("mention command=%r channel=%s team=%s", command, channel_id, team_id)

    try:
        if command in ("help", ""):
            await client.chat_postMessage(channel=channel_id, text=_HELP_TEXT)
            return

        if command == "show":
            text = await _handle_show(team_id)
            await client.chat_postMessage(channel=channel_id, text=text)
            return

        if command == "init":
            await client.chat_postMessage(
                channel=channel_id,
                text="Initializing Forest\u2026 I\u2019ll post here when it\u2019s done.",
            )
            asyncio.create_task(
                _run_onboarding(team_id, force=False, channel_id=channel_id)
            )
            return

        if command == "update":
            await client.chat_postMessage(
                channel=channel_id,
                text="Updating Forest\u2026 I\u2019ll post here when it\u2019s done.",
            )
            asyncio.create_task(
                _run_onboarding(team_id, force=True, channel_id=channel_id)
            )
            return

        await client.chat_postMessage(
            channel=channel_id,
            text=f"Unknown command: `{command}`. Try mentioning me with `help`.",
        )
    except Exception:
        _log.exception(
            "mention handler failed",
            extra={"operation": "mention", "command": command, "workspace_key": team_id},
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/slack/events")
async def slack_events(request: Request) -> Response:
    """Slack Events API endpoint: url_verification, message ingest, and mention commands."""
    body_bytes = await request.body()
    try:
        data = json.loads(body_bytes)
    except Exception:
        return Response(status_code=400)

    if data.get("type") == "url_verification":
        return Response(
            content=json.dumps({"challenge": data.get("challenge", "")}),
            media_type="application/json",
        )

    if request.headers.get("X-Slack-Retry-Num"):
        _log.debug("ignoring Slack retry #%s", request.headers["X-Slack-Retry-Num"])
        return Response(status_code=200)

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not _verify_signature(body_bytes, timestamp, signature):
        return Response(status_code=401)

    if data.get("type") == "event_callback":
        event = data.get("event", {})
        team_id = data.get("team_id", "")

        if event.get("type") == "app_mention" and not event.get("bot_id"):
            asyncio.create_task(_handle_mention(event, team_id))

        elif event.get("type") == "message" and not event.get("subtype") and not event.get("bot_id"):
            asyncio.create_task(_run_ingest(event, team_id))

    return Response(status_code=200)
