"""
Initial database schema for Forest MVP.

Creates the ``vector`` extension (pgvector), ``workspaces``, and ``file_nodes`` with
indexes for multi-tenancy, unique paths per workspace, and optional dedup keys.

Revision ID: e2b3f001
Revises: None
Create Date: 2025-03-20

Notes
-----
Embedding column is ``vector(768)`` — a compact default (see ``EMBEDDING_VECTOR_DIMENSIONS``
in ``forest/models/file_node.py``). The app sends ``dimensions=768`` on embedding API
requests for models that support it (e.g. OpenAI ``text-embedding-3-small``). Changing
``N`` requires a new migration and optional re-embedding.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ENUM

revision: str = "e2b3f001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply extension, enum, tables, and indexes."""
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Create the PG enum once; use create_type=False on the column so create_table
    # does not emit CREATE TYPE again (duplicate without this).
    node_type_enum = ENUM("directory", "file", name="node_type_enum", create_type=True)
    node_type_enum.create(op.get_bind(), checkfirst=True)
    node_type_column = ENUM("directory", "file", name="node_type_enum", create_type=False)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("platform_workspace_id", sa.String(length=64), nullable=False),
        sa.Column("is_initialized", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workspaces_platform_workspace_id",
        "workspaces",
        ["platform", "platform_workspace_id"],
        unique=True,
    )

    op.create_table(
        "file_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("node_type", node_type_column, nullable=False),
        sa.Column("full_path", sa.String(length=2048), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("message_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("external_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["file_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_file_nodes_workspace_id", "file_nodes", ["workspace_id"], unique=False)
    op.create_index("ix_file_nodes_parent_id", "file_nodes", ["parent_id"], unique=False)
    op.create_index(
        "ix_file_nodes_workspace_full_path",
        "file_nodes",
        ["workspace_id", "full_path"],
        unique=True,
    )
    op.create_index(
        "ix_file_nodes_workspace_external_key",
        "file_nodes",
        ["workspace_id", "external_key"],
        unique=True,
        postgresql_where=sa.text("external_key IS NOT NULL"),
    )


def downgrade() -> None:
    """Drop MVP tables, enum, and extension (destructive)."""
    op.drop_index("ix_file_nodes_workspace_external_key", table_name="file_nodes")
    op.drop_index("ix_file_nodes_workspace_full_path", table_name="file_nodes")
    op.drop_index("ix_file_nodes_parent_id", table_name="file_nodes")
    op.drop_index("ix_file_nodes_workspace_id", table_name="file_nodes")
    op.drop_table("file_nodes")
    op.drop_index("ix_workspaces_platform_workspace_id", table_name="workspaces")
    op.drop_table("workspaces")
    ENUM("directory", "file", name="node_type_enum", create_type=False).drop(
        op.get_bind(), checkfirst=True
    )
    op.execute(sa.text("DROP EXTENSION IF EXISTS vector"))
