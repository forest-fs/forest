"""
Alembic environment: offline/online migrations against Forest ORM metadata.

Uses ``DATABASE_URL`` from the environment. Async SQLAlchemy URLs with ``+asyncpg``
are rewritten to ``+psycopg2`` so Alembic can run synchronously (dev dependency).
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from forest.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sync_database_url() -> str:
    """
    Return a synchronous SQLAlchemy URL suitable for Alembic's default engine.

    Returns
    -------
    str
        ``DATABASE_URL`` with ``+asyncpg`` replaced by ``+psycopg2``.

    Raises
    ------
    RuntimeError
        If ``DATABASE_URL`` is unset.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is required for Alembic")
    return url.replace("+asyncpg", "+psycopg2")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script generation / no DB connection)."""
    url = get_sync_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live connection from ``sqlalchemy.url``)."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_sync_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
