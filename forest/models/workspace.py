"""
``Workspace`` model: one row per platform workspace (e.g. Discord guild).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forest.models.base import Base

if TYPE_CHECKING:
    from forest.models.file_node import FileNode


class Workspace(Base):
    """
    Tenant root: maps an external workspace (guild/team) to Forest state.

    Attributes
    ----------
    id : uuid.UUID
        Primary key.
    platform : str
        Adapter name today ``"discord"``; reserved for future platforms.
    platform_workspace_id : str
        Opaque platform id (e.g. Discord guild id as string).
    is_initialized : bool
        When true, onboarding has created the virtual root and seeded directories.
    created_at, updated_at : datetime
        Timestamps maintained by the database / ORM.

    Notes
    -----
    Uniqueness of ``(platform, platform_workspace_id)`` is enforced in migrations.
    All ``FileNode`` queries must filter by ``workspace_id`` for multi-tenancy.
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="discord")
    platform_workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    is_initialized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    file_nodes: Mapped[list[FileNode]] = relationship(
        "FileNode", back_populates="workspace", cascade="all, delete-orphan"
    )
