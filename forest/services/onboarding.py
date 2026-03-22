"""
Phase 0 onboarding: LLM-proposed folder tree, persisted as directory ``FileNode`` rows.

Triggered via the ``@forest init`` mention command (admin).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from forest.repositories.file_node_repo import FileNodeRepository
from forest.repositories.workspace_repo import WorkspaceRepository
from forest.schemas.llm_io import BaseTreeFolder
from forest.services.llm.service import LLMService

_log = logging.getLogger(__name__)


async def seed_folder_tree(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    folders: list[BaseTreeFolder],
) -> None:
    """
    Materialize a recursive folder spec under the workspace root (DFS).

    Parameters
    ----------
    session : AsyncSession
        Database session (transaction owned by caller).
    workspace_id : uuid.UUID
        Workspace primary key.
    folders : list of BaseTreeFolder
        Top-level folders from :class:`~forest.schemas.llm_io.BaseTreeOutput`.

    Notes
    -----
    Does not create embeddings for directories. Root must exist (caller typically
    invokes :meth:`~forest.repositories.file_node_repo.FileNodeRepository.ensure_root`
    first).
    """
    files = FileNodeRepository(session)
    await files.ensure_root(workspace_id)

    async def dfs(parent_full: str, node: BaseTreeFolder) -> None:
        """Depth-first ensure of directory rows (idempotent; safe for re-runs)."""
        path = f"{parent_full.rstrip('/')}/{node.name}" if parent_full != "/" else f"/{node.name}"
        await files.ensure_path(workspace_id, path)
        for child in node.children:
            await dfs(path, child)

    for top in folders:
        await dfs("/", top)


async def run_onboarding_for_workspace(
    session: AsyncSession,
    *,
    platform: str,
    platform_workspace_id: str,
    text_channel_names: list[str],
    workspace_name: str | None,
    llm: LLMService,
    force: bool = False,
    channel_histories: list[dict[str, Any]] | None = None,
) -> bool:
    """
    Run onboarding LLM + DB seed in one flow.

    Parameters
    ----------
    session : AsyncSession
        Active session; commit/rollback is the caller's responsibility (e.g. ``session_scope``).
    platform : str
        Platform key (``"slack"``).
    platform_workspace_id : str
        External workspace id (Slack team_id string).
    text_channel_names : list of str
        Channel (and thread) labels hinting folder topics for the LLM.
    channel_histories : list of dict, optional
        Per-channel message excerpts (e.g. from Slack history scan). When omitted,
        the LLM uses only ``text_channel_names``.
    workspace_name : str or None
        Optional server display name for prompts.
    llm : LLMService
        OpenRouter-backed client.
    force : bool, optional
        If true, re-run the LLM tree step and **merge** any new folders into the
        existing tree (idempotent ``ensure_path``; does not delete files or
        directories). Use after config/schema fixes or to refresh folder hints from
        current channel names and message history (when histories are supplied).

    Returns
    -------
    bool
        ``True`` if onboarding or refresh ran, ``False`` if skipped (already
        initialized and ``force`` is false).

    Notes
    -----
    On success, sets ``is_initialized=True`` on the workspace row. A refresh
    (``force=True``) does not remove prior nodes; it only adds missing directories
    from the new LLM output.
    """
    workspaces = WorkspaceRepository(session)
    files = FileNodeRepository(session)
    ws = await workspaces.upsert_workspace(
        platform=platform, platform_workspace_id=platform_workspace_id
    )
    already_initialized = ws.is_initialized
    if already_initialized and not force:
        _log.info(
            "onboarding skipped: already initialized",
            extra={
                "operation": "onboarding",
                "workspace_id": str(ws.id),
                "workspace_key": platform_workspace_id,
            },
        )
        return False

    tree = await llm.generate_base_tree(
        text_channel_names,
        workspace_name,
        channel_histories=channel_histories,
    )
    await files.ensure_root(ws.id)
    await seed_folder_tree(session, workspace_id=ws.id, folders=tree.folders)
    await workspaces.mark_initialized(ws.id)
    _log.info(
        "onboarding refresh complete" if force and already_initialized else "onboarding complete",
        extra={
            "operation": "onboarding_refresh" if force and already_initialized else "onboarding",
            "workspace_id": str(ws.id),
            "workspace_key": platform_workspace_id,
            "force": force,
        },
    )
    return True
