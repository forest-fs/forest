"""
Workspace persistence: upsert by platform ids, fetch, mark initialized after onboarding.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forest.models.workspace import Workspace


class WorkspaceRepository:
    """
    CRUD-style access to :class:`~forest.models.workspace.Workspace` rows.

    Parameters
    ----------
    session : AsyncSession
        Active SQLAlchemy async session (caller manages transaction boundaries).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_workspace(
        self,
        *,
        platform: str,
        platform_workspace_id: str,
    ) -> Workspace:
        """
        Return existing workspace or insert a new one with ``is_initialized=False``.

        Parameters
        ----------
        platform : str
            Platform key, e.g. ``"discord"``.
        platform_workspace_id : str
            External workspace id (guild id string in the MVP).

        Returns
        -------
        Workspace
            Persisted or existing row (flushed so ``id`` is available).
        """
        stmt = select(Workspace).where(
            Workspace.platform == platform,
            Workspace.platform_workspace_id == platform_workspace_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return row
        ws = Workspace(
            id=uuid.uuid4(),
            platform=platform,
            platform_workspace_id=platform_workspace_id,
            is_initialized=False,
        )
        self._session.add(ws)
        await self._session.flush()
        return ws

    async def get_by_platform_ids(
        self,
        platform: str,
        platform_workspace_id: str,
    ) -> Workspace | None:
        """
        Load a workspace by composite natural key, if present.

        Parameters
        ----------
        platform : str
            Platform key.
        platform_workspace_id : str
            External workspace id.

        Returns
        -------
        Workspace or None
            Matching row or ``None``.
        """
        stmt = select(Workspace).where(
            Workspace.platform == platform,
            Workspace.platform_workspace_id == platform_workspace_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_initialized(self, workspace_id: uuid.UUID) -> None:
        """
        Set ``is_initialized=True`` after successful onboarding.

        Parameters
        ----------
        workspace_id : uuid.UUID
            Primary key of the workspace.

        Notes
        -----
        No-op if the row is missing (should not happen in normal control flow).
        """
        ws = await self._session.get(Workspace, workspace_id)
        if ws is None:
            return
        ws.is_initialized = True
        await self._session.flush()
