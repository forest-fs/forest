"""
``FileNode`` model: directory or file in the virtual tree, optional pgvector embedding.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forest.models.base import Base

if TYPE_CHECKING:
    from forest.models.workspace import Workspace

# Embedding column dimension; must match DB migration(s) and ``EMBEDDING_MODEL_ID`` output.
# Default **768** keeps pgvector storage small; use ``text-embedding-3-small`` (or similar)
# with the API ``dimensions`` parameter — see ``LLMService.embed_summary`` and
# docs/llm-configuration.md.
EMBEDDING_VECTOR_DIMENSIONS = 768


class NodeType(str, enum.Enum):
    """Whether a row is a virtual directory or a captured file leaf."""

    directory = "directory"
    file = "file"


class FileNode(Base):
    """
    Node in the adjacency-list tree under a :class:`Workspace`.

    Attributes
    ----------
    workspace_id : uuid.UUID
        Owning workspace (multi-tenant filter required on all queries).
    parent_id : uuid.UUID or None
        Parent directory; ``None`` only for the virtual root row per workspace.
    name : str
        Final path segment (directory or file name); root uses ``""``.
    node_type : NodeType
        ``directory`` or ``file``.
    full_path : str
        Normalized absolute path string (leading ``/``), unique per workspace.
    source_url, message_url : str or None
        Link to hosted content and/or jump link back to the chat message.
    summary : str or None
        Short LLM summary for files; directories may be null in MVP.
    embedding : list[float] or None
        Vector for future semantic search; stored on ingest for files.

    Notes
    -----
    ``external_key`` supports idempotent ingest (same URL + message id). The database
    enforces a partial unique index on ``(workspace_id, external_key)`` when set.
    """

    __tablename__ = "file_nodes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("file_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    node_type: Mapped[NodeType] = mapped_column(
        SQLEnum(NodeType, name="node_type_enum"),
        nullable=False,
    )
    full_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_VECTOR_DIMENSIONS),
        nullable=True,
    )
    external_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="file_nodes")
    parent: Mapped[FileNode | None] = relationship(
        back_populates="children",
        remote_side=[id],
    )
    children: Mapped[list[FileNode]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
    )
