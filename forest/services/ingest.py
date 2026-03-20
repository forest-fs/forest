"""
Ingest pipeline: map each attachment/URL cue to a routed path, summary, embedding, and DB row.

Platform adapters enqueue :class:`~forest.integrations.types.IngestPayload`; this module
performs LLM routing (OpenRouter), path normalization, and persistence.
"""

from __future__ import annotations

import hashlib
import logging
import re

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from forest.integrations.types import IngestPayload
from forest.repositories.file_node_repo import FileNodeRepository
from forest.repositories.workspace_repo import WorkspaceRepository
from forest.services.llm.service import LLMService
from forest.services.path_utils import (
    leaf_name_from_path,
    normalize_full_path,
    parent_full_path,
)

_log = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    """
    Extract unique HTTP(S) URLs from free text (order preserved, deduplicated).

    Parameters
    ----------
    text : str
        Raw message body.

    Returns
    -------
    list of str
        URLs in first-seen order.
    """
    return list(dict.fromkeys(_URL_RE.findall(text)))


def _transcript_from_payload(payload: IngestPayload) -> str:
    """Build a compact transcript for routing (capped length for token budget)."""
    lines = [f"{ln.author_display}: {ln.text}" for ln in payload.context_lines]
    if payload.message_text.strip():
        lines.append(f"{payload.author_display}: {payload.message_text}")
    body = "\n".join(lines)
    return body[:8000]


def _external_key(source_url: str, message_id: str) -> str:
    """
    Compute a stable dedup key for a cue within a message.

    Parameters
    ----------
    source_url : str
        Attachment or link URL.
    message_id : str
        Platform message id.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest (fits ``external_key`` column).
    """
    raw = f"{source_url}|{message_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def ingest_single_file(
    session: AsyncSession,
    *,
    guild_id: str,
    llm: LLMService,
    payload: IngestPayload,
    cue_title: str,
    source_url: str,
) -> None:
    """
    Route and persist a single cue (attachment or URL) for one ingest payload.

    Parameters
    ----------
    session : AsyncSession
        Session scoped to this cue's transaction.
    guild_id : str
        Discord guild id (matches ``payload.workspace_key`` in MVP).
    llm : LLMService
        Client for chat routing and embeddings.
    payload : IngestPayload
        Canonical message context and metadata.
    cue_title : str
        Human/LLM-facing title (often filename or URL).
    source_url : str
        Canonical URL for the shared asset.

    Notes
    -----
    No-op if workspace is missing or not initialized, if dedup finds an existing file,
    or if a unique constraint triggers ``IntegrityError`` (rolled back for this cue).

    On routing failure, falls back to ``/Inbox`` with a generic summary before embedding.
    """
    ws_repo = WorkspaceRepository(session)
    files = FileNodeRepository(session)
    ws = await ws_repo.get_by_platform_ids(payload.platform, guild_id)
    if ws is None or not ws.is_initialized:
        _log.debug(
            "ingest skipped: workspace missing or not initialized",
            extra={
                "operation": "ingest",
                "guild_id": guild_id,
            },
        )
        return

    ext_key = _external_key(source_url, payload.message_id)
    existing = await files.find_file_by_external_key(ws.id, ext_key)
    if existing is not None:
        return

    dirs = await files.list_directory_paths(ws.id)
    transcript = _transcript_from_payload(payload)
    try:
        route = await llm.route_file(
            context_transcript=transcript,
            cue_title=cue_title,
            source_url=source_url,
            directory_paths=dirs,
        )
    except Exception:
        _log.exception(
            "route_file failed; using Inbox fallback",
            extra={
                "operation": "ingest",
                "workspace_id": str(ws.id),
                "guild_id": guild_id,
                "llm_backend": "openrouter",
            },
        )
        safe_name = cue_title.replace("/", "_")[:200] or "link"
        target = normalize_full_path(f"/Inbox/{safe_name}")
        summary = "Unclassified item"
        parent_path = parent_full_path(target)
        leaf = leaf_name_from_path(target)
        parent_node = await files.ensure_path(ws.id, parent_path)
        embedding = await llm.embed_summary(summary)
        try:
            await files.insert_file(
                workspace_id=ws.id,
                parent_id=parent_node.id,
                name=leaf,
                full_path=target,
                source_url=source_url,
                message_url=payload.message_url,
                summary=summary,
                embedding=embedding,
                external_key=ext_key,
            )
        except IntegrityError:
            await session.rollback()
        return

    target_path = normalize_full_path(route.target_path)
    if route.suggested_name.strip():
        try:
            parent = parent_full_path(target_path)
            target_path = normalize_full_path(f"{parent}/{route.suggested_name.strip()}")
        except ValueError:
            pass
    try:
        leaf = leaf_name_from_path(target_path)
        parent_path = parent_full_path(target_path)
    except ValueError:
        safe_name = route.suggested_name.strip() or cue_title.replace("/", "_")[:200] or "file"
        target_path = normalize_full_path(f"/Inbox/{safe_name}")
        leaf = leaf_name_from_path(target_path)
        parent_path = parent_full_path(target_path)

    summary = route.one_sentence_summary.strip() or f"Shared: {cue_title}"
    parent_node = await files.ensure_path(ws.id, parent_path)
    embedding = await llm.embed_summary(summary)
    try:
        await files.insert_file(
            workspace_id=ws.id,
            parent_id=parent_node.id,
            name=leaf,
            full_path=target_path,
            source_url=source_url,
            message_url=payload.message_url,
            summary=summary,
            embedding=embedding,
            external_key=ext_key,
        )
    except IntegrityError:
        await session.rollback()


async def process_ingest(payload: IngestPayload, llm: LLMService) -> None:
    """
    Process all cues in a payload, one database transaction per cue.

    Parameters
    ----------
    payload : IngestPayload
        Inbound work unit from the Discord adapter.
    llm : LLMService
        OpenRouter-backed LLM client.

    Notes
    -----
    Uses :func:`forest.db.session.session_scope` per cue so partial success is allowed
    when one insert fails on constraints.
    """
    from forest.db.session import session_scope

    guild_id = payload.workspace_key
    cues: list[tuple[str, str]] = []
    for att in payload.attachments:
        cues.append((att.filename or "attachment", att.url))
    for url in payload.link_urls:
        cues.append((url, url))
    if not cues:
        return
    for title, url in cues:
        async with session_scope() as session:
            await ingest_single_file(
                session,
                guild_id=guild_id,
                llm=llm,
                payload=payload,
                cue_title=title,
                source_url=url,
            )
