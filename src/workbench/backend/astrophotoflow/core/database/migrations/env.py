"""Alembic environment.

Online migrations reuse the connection the caller opened on its engine, so the
workspace never needs a second database URL configuration to keep in sync.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
target_metadata = None


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as owned:
        _run(owned)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
