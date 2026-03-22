"""
Virtual tree persistence: root, directory creation, path materialization, file insert, queries.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forest.models.file_node import FileNode, NodeType
from forest.services.path_utils import normalize_full_path, segments_under_root


class FileNodeRepository:
    """
    Operations on :class:`~forest.models.file_node.FileNode` within one workspace.

    Parameters
    ----------
    session : AsyncSession
        Active SQLAlchemy async session.

    Notes
    -----
    All public methods assume ``workspace_id`` filters to prevent cross-tenant access.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_root(self, workspace_id: uuid.UUID) -> FileNode | None:
        """
        Return the virtual root directory row for a workspace, if it exists.

        Parameters
        ----------
        workspace_id : uuid.UUID
            Owning workspace primary key.

        Returns
        -------
        FileNode or None
            Row with ``full_path='/'``, ``parent_id IS NULL``, ``directory`` type.
        """
        stmt = select(FileNode).where(
            FileNode.workspace_id == workspace_id,
            FileNode.parent_id.is_(None),
            FileNode.node_type == NodeType.directory,
            FileNode.full_path == "/",
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def ensure_root(self, workspace_id: uuid.UUID) -> FileNode:
        """
        Return the root directory, creating it on first use.

        Parameters
        ----------
        workspace_id : uuid.UUID
            Owning workspace.

        Returns
        -------
        FileNode
            Root directory row.
        """
        existing = await self.get_root(workspace_id)
        if existing:
            return existing
        root = FileNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            parent_id=None,
            name="",
            node_type=NodeType.directory,
            full_path="/",
            source_url=None,
            message_url=None,
            summary=None,
            embedding=None,
            external_key=None,
        )
        self._session.add(root)
        await self._session.flush()
        return root

    async def find_child_directory(
        self,
        *,
        workspace_id: uuid.UUID,
        parent_id: uuid.UUID,
        name: str,
    ) -> FileNode | None:
        """
        Find an existing child **directory** by name under a parent.

        Parameters
        ----------
        workspace_id : uuid.UUID
            Workspace scope.
        parent_id : uuid.UUID
            Parent directory id.
        name : str
            Child segment name.

        Returns
        -------
        FileNode or None
            Matching directory or ``None``.
        """
        stmt = select(FileNode).where(
            FileNode.workspace_id == workspace_id,
            FileNode.parent_id == parent_id,
            FileNode.name == name,
            FileNode.node_type == NodeType.directory,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_directory(
        self,
        *,
        workspace_id: uuid.UUID,
        parent_id: uuid.UUID,
        name: str,
        full_path: str,
        summary: str | None = None,
    ) -> FileNode:
        """
        Insert a new directory node under ``parent_id``.

        Parameters
        ----------
        workspace_id : uuid.UUID
            Owning workspace.
        parent_id : uuid.UUID
            Parent directory id.
        name : str
            Final path segment.
        full_path : str
            Absolute normalized path; coerced via
            :func:`~forest.services.path_utils.normalize_full_path`.
        summary : str or None
            Optional LLM blurb; null in MVP onboarding.

        Returns
        -------
        FileNode
            Flushed directory row.
        """
        node = FileNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            parent_id=parent_id,
            name=name,
            node_type=NodeType.directory,
            full_path=normalize_full_path(full_path),
            source_url=None,
            message_url=None,
            summary=summary,
            embedding=None,
            external_key=None,
        )
        self._session.add(node)
        await self._session.flush()
        return node

    async def ensure_path(self, workspace_id: uuid.UUID, full_path: str) -> FileNode:
        """
        Ensure all directory segments along ``full_path`` exist (idempotent).

        Parameters
        ----------
        workspace_id : uuid.UUID
            Owning workspace.
        full_path : str
            **Directory** path (e.g. ``/Docs/2024``), not a file path.

        Returns
        -------
        FileNode
            The directory node for ``full_path`` (root if ``full_path`` is ``/``).

        Notes
        -----
        Walks segments from the virtual root, creating missing directories. Does not
        create a file leaf; callers use :meth:`insert_file` after computing parent path.
        """
        norm = normalize_full_path(full_path)
        root = await self.ensure_root(workspace_id)
        if norm == "/":
            return root
        segments = segments_under_root(norm)
        current = root
        accumulated = ""
        for segment in segments:
            # Build absolute path string for this directory level (e.g. /a then /a/b).
            accumulated = f"{accumulated}/{segment}" if accumulated else f"/{segment}"
            child = await self.find_child_directory(
                workspace_id=workspace_id, parent_id=current.id, name=segment
            )
            if child is None:
                child = await self.create_directory(
                    workspace_id=workspace_id,
                    parent_id=current.id,
                    name=segment,
                    full_path=accumulated,
                )
            current = child
        return current

    async def insert_file(
        self,
        *,
        workspace_id: uuid.UUID,
        parent_id: uuid.UUID,
        name: str,
        full_path: str,
        source_url: str | None,
        message_url: str | None,
        summary: str | None,
        embedding: Sequence[float] | None,
        external_key: str | None = None,
    ) -> FileNode:
        """
        Insert a **file** leaf under an existing parent directory.

        Parameters
        ----------
        workspace_id : uuid.UUID
            Owning workspace.
        parent_id : uuid.UUID
            Parent directory id (from :meth:`ensure_path` on the parent folder).
        name : str
            Leaf file name segment.
        full_path : str
            Absolute file path, normalized.
        source_url, message_url : str or None
            Link to content and/or chat jump URL.
        summary : str or None
            One-sentence summary for display / future search.
        embedding : sequence of float or None
            Vector from ``EMBEDDING_MODEL_ID``; length must match DB column.
        external_key : str or None
            Dedup key (hash of url + message id) when provided.

        Returns
        -------
        FileNode
            Flushed file row.

        Raises
        ------
        sqlalchemy.exc.IntegrityError
            On unique violations (e.g. duplicate ``full_path`` or ``external_key``).
        """
        node = FileNode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            parent_id=parent_id,
            name=name,
            node_type=NodeType.file,
            full_path=normalize_full_path(full_path),
            source_url=source_url,
            message_url=message_url,
            summary=summary,
            embedding=list(embedding) if embedding is not None else None,
            external_key=external_key,
        )
        self._session.add(node)
        await self._session.flush()
        return node

    async def list_directory_paths(self, workspace_id: uuid.UUID) -> list[str]:
        """
        Return sorted absolute paths of all directories (for LLM routing context).

        Parameters
        ----------
        workspace_id : uuid.UUID
            Workspace scope.

        Returns
        -------
        list of str
            ``full_path`` values for ``node_type=directory``.
        """
        stmt = (
            select(FileNode.full_path)
            .where(
                FileNode.workspace_id == workspace_id,
                FileNode.node_type == NodeType.directory,
            )
            .order_by(FileNode.full_path)
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def list_files_flat(self, workspace_id: uuid.UUID) -> list[FileNode]:
        """
        Return all **file** nodes sorted by ``full_path`` (for ``@forest show`` listing).

        Parameters
        ----------
        workspace_id : uuid.UUID
            Workspace scope.

        Returns
        -------
        list of FileNode
            File leaves only.
        """
        stmt = (
            select(FileNode)
            .where(
                FileNode.workspace_id == workspace_id,
                FileNode.node_type == NodeType.file,
            )
            .order_by(FileNode.full_path)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_file_by_external_key(
        self, workspace_id: uuid.UUID, external_key: str
    ) -> FileNode | None:
        """
        Look up an existing file by dedup key within a workspace.

        Parameters
        ----------
        workspace_id : uuid.UUID
            Workspace scope.
        external_key : str
            Stable hash from ingest (URL + message id).

        Returns
        -------
        FileNode or None
            Existing row or ``None``.
        """
        stmt = select(FileNode).where(
            FileNode.workspace_id == workspace_id,
            FileNode.external_key == external_key,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
