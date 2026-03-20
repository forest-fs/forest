"""
Optional DB integration tests (Postgres + pgvector + migrations).

Enable with ``FOREST_RUN_DB_INTEGRATION=1`` after ``docker compose up`` and
``alembic upgrade head``.
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("FOREST_RUN_DB_INTEGRATION") != "1",
    reason=(
        "Set FOREST_RUN_DB_INTEGRATION=1 with Postgres (docker compose) and alembic upgrade head"
    ),
)


@pytest.mark.asyncio
async def test_ensure_path_and_file_roundtrip() -> None:
    """
    Ensure :meth:`ensure_path` creates parents and :meth:`insert_file` persists a leaf.

    Requires a live database matching ``DATABASE_URL`` and applied migrations.
    """
    from forest.db.session import async_session_factory
    from forest.repositories.file_node_repo import FileNodeRepository
    from forest.repositories.workspace_repo import WorkspaceRepository

    async with async_session_factory() as session:
        wr = WorkspaceRepository(session)
        fr = FileNodeRepository(session)
        ws = await wr.upsert_workspace(platform="discord", platform_workspace_id=str(uuid.uuid4()))
        await fr.ensure_root(ws.id)
        parent = await fr.ensure_path(ws.id, "/Docs/2024")
        await fr.insert_file(
            workspace_id=ws.id,
            parent_id=parent.id,
            name="readme.md",
            full_path="/Docs/2024/readme.md",
            source_url="https://example.com/x",
            message_url="https://discord.com/channels/1/2/3",
            summary="A doc",
            embedding=[0.0] * 3072,
            external_key="k1",
        )
        await session.commit()

    async with async_session_factory() as session:
        fr = FileNodeRepository(session)
        files = await fr.list_files_flat(ws.id)
        assert len(files) == 1
        assert files[0].full_path == "/Docs/2024/readme.md"
