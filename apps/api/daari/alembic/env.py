"""Async Alembic env. Reads DATABASE_URL from daari.config.Settings — never hardcoded here.

The P2 vector tables are managed by a hand-written migration. Other model
metadata is still absent, so target_metadata remains None.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from daari.config import settings
from daari.db import _connect_args, _to_asyncpg_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _asyncpg_url() -> str:
    return _to_asyncpg_url(settings.database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=_asyncpg_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _asyncpg_url()
    connectable = async_engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool,
        connect_args=_connect_args(settings.database_url),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
