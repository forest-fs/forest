"""
Widen ``file_nodes.embedding`` to vector(3072).

Many OpenRouter embedding models (for example ``text-embedding-3-large``) return
3072 dimensions; the initial migration used 1536 for smaller models.

Revision ID: e2b3f002
Revises: e2b3f001
Create Date: 2026-03-20

Notes
-----
If you already stored non-null embeddings as 1536-dimensional vectors, you must
re-embed or clear those rows before this ALTER; otherwise PostgreSQL may reject
the type change. Fresh installs or tables with only failed inserts (NULL
attachments) typically migrate cleanly.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2b3f002"
down_revision: Union[str, None] = "e2b3f001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE file_nodes ALTER COLUMN embedding TYPE vector(3072)"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE file_nodes ALTER COLUMN embedding TYPE vector(1536)"))
